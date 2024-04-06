from concurrent.futures import ThreadPoolExecutor
import shutil
import subprocess
import yt_dlp
import re
from pathlib import Path
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
    'retries': 30,
    'continuedl': True,
    'extractor_retries': 30,
  }
  if session:
    options['http_headers'] = session.headers

  return options


def download_with_retries(ydl_opts, media):
  try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
      ydl.download([media])
  except yt_dlp.utils.DownloadError as e:
    msg = f'''Verifique manualmente, se não baixou tente novamente mais tarde: {ydl_opts['outtmpl']} ||| {media} ||| {e}'''
    logger(msg, warning=True)


def process_webinar(webinar_folder, index, webinar, session):
  response = connect(webinar, session)
  response = session.get(webinar).json()
  webinar_link, webinar_title = response['url'], response['name']
  webinar_folder = concat_path(webinar_folder, f'{index:03d} - {webinar_title}.mp4')
  download_complementary(webinar_folder, webinar_link)


def process_complementary_readings(complementary_folder, complementary_url, complementarys_name, session):
  if 'youtube' in complementary_url or 'youtu.be' in complementary_url:
    new_complementary_folder = shorten_folder_name(concat_path(complementary_folder, f'{complementarys_name}.mp4'))
    download_complementary(new_complementary_folder, complementary_url)
  elif complementary_url:
    save_link(complementary_folder, complementary_url, complementarys_name)


def download_iframe_video_task(output_path, video_url, session, headers=None):
  if headers:
    session.headers.update(headers)
  download_complementary(output_path, video_url, session)


def download_video(path, index, lesson_video, session):
  output = shorten_folder_name(concat_path(path, f'{index:03} - aula.mp4'))
  ydl_opts = ytdlp_options(output, session)
  with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([lesson_video])


def download_file(path, attachments):
  with open(shorten_folder_name(path), 'wb') as file:
    for chunk in attachments.iter_content(chunk_size=8192):
      file.write(chunk)


def download_attachments(material_folder, attachment_id, attachment_name, session):
  response = session.get(f'https://api-club.cb.hotmart.com/rest/v3/attachment/{attachment_id}/download?attachmentId={attachment_id}').json()
  if response.get('directDownloadUrl'):
    attachments_url = response['directDownloadUrl']
    attachments = requests.get(attachments_url, stream=True)
    path = concat_path(material_folder, clear_folder_name(attachment_name, is_file=True))
    download_file(path, attachments)
  elif response.get('lambdaUrl'):
    session.headers['authority'] = 'drm-protection.cb.hotmart.com'
    session.headers['token'] = response.get('token')
    attachments_url = connect('https://drm-protection.cb.hotmart.com', session).text
    attachments = connect(attachments_url, session)
    path = concat_path(material_folder, clear_folder_name(attachment_name, is_file=True))
    download_file(path, attachments)
    logger(f'Verifique o arquivo manualmente, pode ter dados importantes: {path}', warning=True)


def save_html(content_folder, html):
  file_path = shorten_folder_name(concat_path(content_folder, 'conteudo.html'))
  if not os.path.exists(file_path):
    with open(file_path, 'w', encoding='utf-8') as file:
      file.write(str(html))


def save_link(complementary_folder, complementary_url, complementarys_name):
  file_path = shorten_folder_name(concat_path(complementary_folder, f'{complementarys_name}.txt'))
  if not os.path.exists(file_path):
    with open(file_path, 'w', encoding='utf-8') as file:
      file.write(str(complementary_url))


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
