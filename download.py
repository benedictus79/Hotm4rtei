import yt_dlp
from utils import concat_path, create_folder, os, shorten_folder_name, clear_folder_name, SilentLogger
from login import requests


def download_video(lessons, session):
  ffmpeg_path = concat_path(os.getcwd(), 'bin', 'ffmpeg.exe')

  for lesson_name, lesson_data in lessons.items():
    output = shorten_folder_name(concat_path(lesson_data['path'], f'{clear_folder_name(lesson_name)}.mp4'))
    ydl_opts = {
    'format': 'bv+ba/b',
    'outtmpl': output,
    'quiet': True,
    'no_progress': True,
    'http_headers': session.headers,
    'logger': SilentLogger(),
    'concurrent_fragment_downloads': 7,
    'fragment_retries': 50,
    'retry_sleep_functions': {'fragment': 30},
    'buffersize': 104857600,
    'retries': 30,
    'continuedl': True,
    'extractor_retries': 30,
    'ffmpeg_location': ffmpeg_path,
    'postprocessors': [{'key': 'FFmpegFixupM3u8'}],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      for lesson_media in lesson_data['media']:
        ydl.download([lesson_media])


def download_attachments(material_folder, attachments, session):
  if attachments:
    for i, attachment in enumerate(attachments, start=1):
      attachments_id = attachment['fileMembershipId']
      filename = attachment['fileName']
      response = session.get(f'https://api-club.cb.hotmart.com/rest/v3/attachment/{attachments_id}/download?attachmentId={attachments_id}').json()['directDownloadUrl']
      attachments = requests.get(response, stream=True)
      path = concat_path(material_folder, f'{i:03d} - {filename}')
      with open(path, 'wb') as file:
        for chunk in attachments.iter_content(chunk_size=8192):
          file.write(chunk)