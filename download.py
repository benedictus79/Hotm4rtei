import platform
import yt_dlp
from utils import concat_path, create_folder, os, shorten_folder_name, clear_folder_name, SilentLogger
from login import requests


def ytdlp_options(output_folder, session=None):
  options = {
    'format': 'bv[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best',
    'outtmpl': output_folder,
    'quiet': True,
    'no_progress': True,
    'logger': SilentLogger(),
    'concurrent_fragment_downloads': 10,
    'fragment_retries': 50,
    'fragment_index': None,
    'retry_sleep_functions': {'fragment': 100},
    'buffersize': 104857600,
    'retries': 60,
    'continuedl': True,
    'extractor_retries': 60,
    'postprocessors': [{'key': 'FFmpegFixupM3u8'}],
    'socket_timeout': 30,
  }
  if session:
    options['http_headers'] = session.headers

  return options


def download_video(lessons, session):
  for lesson_name, lesson_data in lessons.items():
    output = shorten_folder_name(concat_path(lesson_data['path'], f'{clear_folder_name(lesson_name)}.mp4'))
    ydl_opts = ytdlp_options(output, session)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      for lesson_media in lesson_data['media']:
        ydl.download([lesson_media])


def download_attachments(material_folder, attachments, session):
  for i, attachment in enumerate(attachments, start=1):
    attachments_id = attachment['fileMembershipId']
    filename = attachment['fileName']
    response = session.get(f'https://api-club.cb.hotmart.com/rest/v3/attachment/{attachments_id}/download?attachmentId={attachments_id}').json()['directDownloadUrl']
    attachments = requests.get(response, stream=True)
    path = concat_path(material_folder, f'{i:03d} - {filename}')
    with open(path, 'wb') as file:
      for chunk in attachments.iter_content(chunk_size=8192):
        file.write(chunk)


def save_html(content_folder, html):
  file_path = shorten_folder_name(os.path.join(content_folder, clear_folder_name('conteudo' + '.html')))

  if not os.path.exists(file_path):
    with open(file_path, 'w', encoding='utf-8') as file:
      file.write(str(html))


def download_complementary(complementary_folder, complementary, session=None):
  ydl_opts = ytdlp_options(complementary_folder)
  if session:
    ydl_opts = ytdlp_options(complementary_folder, session)
  with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([complementary])


def is_vimeo_iframe(iframe):
  return iframe is not None and 'src' in iframe.attrs and 'vimeo' in iframe['src']
