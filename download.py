from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import yt_dlp
import re
from connection import check_forbidden, connect
from login import requests
from utils import concat_path, logger, os, random_sleep, shorten_folder_name, clear_folder_name, SilentLogger


success_hdntl_lock = Lock()
success_hdntl = None


def ytdlp_options(output_folder, session=None):
  options = {
    'format': 'bv[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best',
    'outtmpl': output_folder,
    'quiet': True,
    'no_progress': True,
    'logger': SilentLogger(),
    'concurrent_fragment_downloads': 10,
    'fragment_retries': 50,
    'retry_sleep_functions': {'fragment': 20},
    'buffersize': 10485760,
    'retries': 20,
    'continuedl': True,
    'hls_prefer_native': False,
    'extractor_retries': 20,
    #'external_downloader': {'m3u8': 'ffmpeg'},
    'postprocessors': [{'key': 'FFmpegFixupM3u8'}],
    'socket_timeout': 60,
    'http_chunk_size': 10485760,
  }
  if session:
    options['http_headers'] = session.headers

  return options


def download_with_retries(ydl_opts, media, max_attempts=3):
  while True:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      try:
        ydl.download([media])
        return
      except yt_dlp.utils.DownloadError as e:
        msg = f'Falha ao baixar, tente novamente mais parte {ydl_opts['outtmpl']}'
        logger(msg, warning=True)
        return
      except PermissionError as e:
        random_sleep()


def download_video(lessons, session):
    def download_task(lesson_name, lesson_media):
        output = shorten_folder_name(concat_path(lessons[lesson_name]['path'], f'{clear_folder_name(lesson_name)}.mp4'))
        ydl_opts = ytdlp_options(output, session)
        download_with_retries(ydl_opts, lesson_media)

    with ThreadPoolExecutor(max_workers=7) as executor:
        for lesson_name, lesson_data in lessons.items():
            # Criar uma lista de tarefas para serem executadas em paralelo
            tasks = [(lesson_name, media) for media in lesson_data['media']]
            # Agendar as tarefas para execução
            for task in tasks:
                executor.submit(download_task, *task)
""" with success_hdntl_lock:
  if download_status == 'sucesso':
    print('Sucesso no download')
    success_hdntl = extract_hdntl(lesson_media)
    print('HDNTL de sucesso:', success_hdntl)
  elif download_status == '403' and success_hdntl is not None:
      new_media = replace_hdntl(lesson_media, success_hdntl)
      retry_status = download_with_retries(ydl_opts, new_media)
      if retry_status == 'sucesso':
          print('Sucesso após tentar novamente') """
    


def download_file(path, attachments):
  with open(path, 'wb') as file:
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
      attachments_url = session.get('https://drm-protection.cb.hotmart.com', stream=True).text
      attachments = session.get(attachments_url, stream=True)
      path = concat_path(material_folder, f'{i:03d} - {filename}')
      download_file(path, attachments)
      logger(f'Verifique o arquivo manualmente, pode ter dados importantes: {path}', warning=True)


def save_html(content_folder, html):
  file_path = shorten_folder_name(concat_path(content_folder, clear_folder_name('conteudo.html')))
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
  download = download_with_retries(ydl_opts, complementary)
  if download == '403':
    ydl_opts = check_forbidden(ydl_opts, complementary, session)
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
