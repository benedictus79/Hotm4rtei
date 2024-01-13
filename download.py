import yt_dlp
import re
from connection import check_forbidden, connect
from login import requests
from utils import concat_path, logger, os, random_sleep, shorten_folder_name, clear_folder_name, SilentLogger


def ytdlp_options(output_folder, session=None):
  options = {
    'format': 'bv[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best',
    'outtmpl': output_folder,
    'quiet': True,
    'no_progress': True,
    'logger': SilentLogger(),
    'concurrent_fragment_downloads': 9,
    'fragment_retries': 50,
    'fragment_index': None,
    'retry_sleep_functions': {'fragment': 10},
    'buffersize': 1024,
    'retries': 20,
    'continuedl': True,
    'extractor_retries': 10,
    'postprocessors': [{'key': 'FFmpegFixupM3u8'}],
    'socket_timeout': 60,
    'http_chunk_size': 10485760,
  }
  if session:
    options['http_headers'] = session.headers

  return options


def download_with_retries(ydl_opts, media, max_attempts=2):
  for attempt in range(max_attempts):
    try:
      if attempt == 1:
        random_sleep()
      with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([media])
      return
    except yt_dlp.utils.DownloadError as e:
      if '403' in str(e):
        random_sleep()
        return '403'
    except Exception as e:
      msg = (f'Erro ao baixar, tentando novamente {media}: {e}' if 'No such file or directory' in str(e) else f'Verifique o arquivo manualmente: {ydl_opts['outtmpl']}') if attempt == max_attempts - 1 else None
      if msg: logger(msg, error=True)


def download_video(lessons, session):
  for lesson_name, lesson_data in lessons.items():
    output = shorten_folder_name(concat_path(lesson_data['path'], f'{clear_folder_name(lesson_name)}.mp4'))
    ydl_opts = ytdlp_options(output, session)
    for lesson_media in lesson_data['media']:
      download = download_with_retries(ydl_opts, lesson_media)
      if download == '403':
        ydl_opts = check_forbidden(ydl_opts, lesson_media, session)
        download_with_retries(ydl_opts, lesson_media)


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
  file_path = shorten_folder_name(os.path.join(content_folder, clear_folder_name('conteudo.html')))
  if not os.path.exists(file_path):
    with open(file_path, 'w', encoding='utf-8') as file:
      file.write(str(html))


def save_link(complementary_folder, index, text_link):
  file_path = shorten_folder_name(os.path.join(complementary_folder, clear_folder_name(f'{index:03d} - complemento.txt')))
  if not os.path.exists(file_path):
    with open(file_path, 'w', encoding='utf-8') as file:
      file.write(str(text_link))


def download_complementary(complementary_folder, complementary, session=None):
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
  pattern = r'v=([a-zA-Z0-9-]+)'
  match = re.search(pattern, url)
  if match:
    extracted_part = match.group(1)
    video_url = f'https://b-vz-ebb1a508-9aa.tv.pandavideo.com.br/{extracted_part}/playlist.m3u8'
    return video_url


def is_pandavideo_iframe(iframe):
  return iframe is not None and 'src' in iframe.attrs and 'pandavideo' in iframe['src']
