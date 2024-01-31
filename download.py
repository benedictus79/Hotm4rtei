from concurrent.futures import ThreadPoolExecutor
import yt_dlp
import re
from connection import connect
from login import requests, BeautifulSoup, course_link
from utils import concat_path, create_folder, logger, os, random_sleep, shorten_folder_name, clear_folder_name, SilentLogger


def ytdlp_options(output_folder, session=None):
  options = {
    'format': 'bv[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best',
    'outtmpl': output_folder,
    'quiet': True,
    'no_progress': True,
    'logger': SilentLogger(),
    'concurrent_fragment_downloads': 10,
    'fragment_retries': 50,
    'file_access_retries': 10,
    'retry_sleep_functions': {'fragment': 20},
    'buffersize': 10485760,
    'retries': 20,
    'continuedl': True,
    'hls_prefer_native': False,
    'extractor_retries': 20,
    'external_downloader': {'m3u8': 'ffmpeg'},
    'postprocessors': [{'key': 'FFmpegFixupM3u8'}],
    'socket_timeout': 60,
    'http_chunk_size': 10485760,
  }
  if session:
    options['http_headers'] = session.headers

  return options


def download_with_retries(ydl_opts, media):
  while True:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      try:
        ydl.download([media])
        return
      except yt_dlp.utils.DownloadError as e:
        if '403' in str(e):
          msg = f'Verifique manualmente, se não baixou tente novamente mais tarde: {ydl_opts['outtmpl']}'
          logger(msg, warning=True)
          return
      except PermissionError as e:
        random_sleep()


def process_webinar(webinar_folder, index, webinar, session):
  response = connect(webinar, session)
  response = session.get(webinar).json()
  webinar_link, webinar_title = response['url'], response['name']
  webinar_folder = concat_path(webinar_folder, f'{index:03d} - {webinar_title}.mp4')
  download_complementary(webinar_folder, webinar_link)


def process_complementary_readings(complementary_folder, complementarys, session):
  for i, complementary in enumerate(complementarys, start=1):
    article_url = complementary.get('articleUrl')
    if article_url and ('youtube' in article_url or 'youtu.be' in article_url):
      complementary_title = clear_folder_name(complementary.get('articleName'))
      new_complementary_folder = shorten_folder_name(concat_path(complementary_folder, f'{i:03d} - {complementary_title}.mp4'))
      download_complementary(new_complementary_folder, article_url)
    elif article_url:
      save_link(complementary_folder, i, article_url)


def download_task(lessons, lesson_name, lesson_media, session):
    output = shorten_folder_name(concat_path(lessons[lesson_name]['path'], f'{clear_folder_name(lesson_name)}.mp4'))
    ydl_opts = ytdlp_options(output, session)
    download_with_retries(ydl_opts, lesson_media)


def download_iframe_video_task(output_path, video_url, session, headers=None):
    if headers:
        session.headers.update(headers)
    download_complementary(output_path, video_url, session)


def download_video(lessons, session):
  with ThreadPoolExecutor(max_workers=5) as executor:
    for lesson_name, lesson_data in lessons.items():
      tasks = [(lessons, lesson_name, media, session) for media in lesson_data['media']]
      for task in tasks:
        executor.submit(download_task, *task)
      if lesson_data.get('complementary_readings'):
        complementary_folder = create_folder(shorten_folder_name(concat_path(lesson_data['path'], 'complemento')))
        process_complementary_readings(complementary_folder, lesson_data['complementary_readings'], session)
      if lesson_data.get('webinar'):
        webinar_folder = create_folder(shorten_folder_name(concat_path(lesson_data['path'], 'webinar')))
        process_webinar(webinar_folder, lesson_name, lesson_data['webinar'], session)
      if lesson_data.get('attachments'):
        material_folder = create_folder(shorten_folder_name(concat_path(lesson_data['path'], 'material')))
        download_attachments(material_folder, lesson_data['attachments'], session)
      if lesson_data.get('content'):
        soup = BeautifulSoup(lesson_data['content'], 'html.parser')
        iframe = soup.find('iframe')
        if iframe and is_vimeo_iframe(iframe):
          video_url = iframe['src']
          output_path = shorten_folder_name(concat_path(lesson_data['path'], f'{lesson_name}.mp4'))
          session.headers['Referer'] = course_link
          executor.submit(download_iframe_video_task, output_path, video_url, session)
        if iframe and is_pandavideo_iframe(iframe):
          video_url = url_conveter_pandavideo(iframe['src'])
          output_path = shorten_folder_name(concat_path(lesson_data['path'], f'{lesson_name}.mp4'))
          session.headers.update(pandavideoheaders(iframe['src']))
          executor.submit(download_iframe_video_task, output_path, video_url, session, pandavideoheaders(iframe['src']))
        content_folder = create_folder(shorten_folder_name(concat_path(lesson_data['path'], 'html')))
        save_html(content_folder, lesson_data['content'])


def download_file(path, attachments):
  with open(shorten_folder_name(path), 'wb') as file:
    for chunk in attachments.iter_content(chunk_size=8192):
      file.write(chunk)


def download_attachments(material_folder, attachments, session):
  for i, attachment in enumerate(attachments, start=1):
    attachments_id = attachment['fileMembershipId']
    filename = attachment['fileName']
    response = session.get(f'https://api-club.cb.hotmart.com/rest/v3/attachment/{attachments_id}/download?attachmentId={attachments_id}').json()
    if response.get('directDownloadUrl'):
      attachments_url = response['directDownloadUrl']
      attachments = requests.get(attachments_url, stream=True)
      path = concat_path(material_folder, f'{i:03d} - {filename}')
      download_file(path, attachments)
    elif response.get('lambdaUrl'):
      session.headers['authority'] = 'drm-protection.cb.hotmart.com'
      session.headers['token'] = response.get('token')
      attachments_url = connect('https://drm-protection.cb.hotmart.com', session).text
      attachments = connect(attachments_url, session)
      path = concat_path(material_folder, f'{i:03d} - {filename}')
      download_file(path, attachments)
      logger(f'Verifique o arquivo manualmente, pode ter dados importantes: {path}', warning=True)


def save_html(content_folder, html):
  file_path = shorten_folder_name(concat_path(content_folder, 'conteudo.html'))
  if not os.path.exists(file_path):
    with open(file_path, 'w', encoding='utf-8') as file:
      file.write(str(html))


def save_link(complementary_folder, index, text_link):
  file_path = shorten_folder_name(concat_path(complementary_folder, f'{index:03d} - complemento.txt'))
  if not os.path.exists(file_path):
    with open(file_path, 'w', encoding='utf-8') as file:
      file.write(str(text_link))


def download_complementary(complementary_folder, complementary, session=None):
  ydl_opts = ytdlp_options(complementary_folder)
  if session:
    ydl_opts = ytdlp_options(complementary_folder, session)
  download_with_retries(ydl_opts, complementary)


def is_vimeo_iframe(iframe):
  return iframe is not None and 'src' in iframe.attrs and 'vimeo' in iframe['src']


pandavideoheaders = lambda rerefer, optional_origin=None: {
  'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Referer': rerefer,
  **({'Origin': optional_origin} if optional_origin is not None else {})
}


def url_conveter_pandavideo(url):
  pattern = r'https://player-vz-([a-zA-Z0-9-]+).tv.pandavideo.com.br/embed/\?v=([a-zA-Z0-9-]+)'
  match = re.search(pattern, url)
  if match:
    subdomain = match.group(1)
    extracted_part = match.group(2)
    video_url = f'https://b-vz-{subdomain}.tv.pandavideo.com.br/{extracted_part}/playlist.m3u8'
    return video_url


def is_pandavideo_iframe(iframe):
  return iframe is not None and 'src' in iframe.attrs and 'pandavideo' in iframe['src']
