import subprocess
import yt_dlp
import re
from connection import connect, connect_license_drm
from login import requests, BeautifulSoup
from utils import concat_path, create_folder, logger, os, random_sleep, shorten_folder_name, clear_folder_name, SilentLogger


def ytdlp_options(output_folder, session=None):
  options = {
    'format': 'bv[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best',
    'outtmpl': f'{output_folder}.%(ext)s',
    'quiet': True,
    'no_progress': True,
    'logger': SilentLogger(),
    'concurrent_fragment_downloads': 10,
    'fragment_retries': 50,
    'file_access_retries': 50,
    'retries': 50,
    'continuedl': True,
    'extractor_retries': 50,
    'trim_file_name': 249,
  }
  if session:
    options['http_headers'] = session.headers

  return options


def download_with_ffmpeg(decryption_key, name_lesson, url):
  if not os.path.exists(f'{name_lesson}.mp4'):
    cmd = [
      'ffmpeg',
      '-cenc_decryption_key', decryption_key,
      '-headers', 'Referer: https://cf-embed.play.hotmart.com/',
      '-y',
      '-i', url,
      '-codec', 'copy',
      '-threads', '4',
      f'{name_lesson}.mp4'
    ]
    return subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def download_with_ytdlp(ydl_opts, media):
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
  webinar_folder = concat_path(webinar_folder, f'{index:03d} - {webinar_title}')
  return download_complementary(webinar_folder, webinar_link)


def process_complementary_readings(complementary_folder, complementary_url, complementarys_name, session):
  if 'youtube' in complementary_url or 'youtu.be' in complementary_url:
    new_complementary_folder = shorten_folder_name(concat_path(complementary_folder, f'{complementarys_name}'))
    return download_complementary(new_complementary_folder, complementary_url)
  elif complementary_url:
    return save_link(complementary_folder, complementary_url, complementarys_name)
  

def get_pssh(response):
  soup = BeautifulSoup(response.text, 'html.parser')
  pssh_element = soup.find('cenc:pssh')
  if pssh_element:
    pssh = pssh_element.text
    return pssh


def get_license(lesson_video, session):
  params = {
    'token': lesson_video['signature'],
    'userCode': lesson_video['userCode'],
    'applicationCode': lesson_video['applicationKey'],
    }
  data = '\b\x04'
  headers = {
    'accept': '*/*',
    'accept-language': 'pt-BR,pt;q=0.7',
    'cache-control': 'no-cache',
    'content-type': 'application/octet-stream',
    'dnt': '1',
    'keysystem': 'com.widevine.alpha',
    'membership': f'{lesson_video["clubMembershipId"]}',
    'origin': 'https://cf-embed.play.hotmart.com',
    'pragma': 'no-cache',
    'referer': 'https://cf-embed.play.hotmart.com/',
  }
  url = f'https://api-player-embed.hotmart.com/v2/drm/{lesson_video["mediaCode"]}/license'
  return connect_license_drm(url, session, params, data, headers)


def get_key_drm(data):
  api_url = 'https://cdrm-project.com/api'
  license_url = data['license']
  pssh = data['pssh']
  json_data = {
    'license': license_url,
    'headers': 'accept: "*/*"\naccept-language: "pt-BR,pt;q=0.7"\ncache-control: no-cache\ncontent-type: application/octet-stream\ndnt: "1"\nkeysystem: com.widevine.alpha\norigin: "https://cf-embed.play.hotmart.com"\npragma: no-cache\nreferer: "https://cf-embed.play.hotmart.com/"\nuser-agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"',
    'pssh': pssh,
    'buildInfo': '',
    'proxy': '',
    'cache': False,
  }
  headers = {
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7,gl;q=0.6,es;q=0.5',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Origin': 'https://cdrm-project.com',
    'Pragma': 'no-cache',
    'Referer': 'https://cdrm-project.com/',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
  }
  r = requests.post(api_url, json=json_data, headers=headers).json()
  decryption_key = r['keys'][0]['key'].split(':')[1]
  return decryption_key


def download_video(path, index, lesson_video, session):
  if 'drm/' in lesson_video['url']:
    response = connect(lesson_video['url'], session)
    pssh = get_pssh(response)
    license = get_license(lesson_video, session)
    wv_data = {
      'license': license,
      'pssh': pssh
    }
    decryption_key = get_key_drm(wv_data)
    name_lesson = shorten_folder_name(concat_path(path, f' {index:03} - aula'))
    logger(f'''Conteúdo com DRM encontrado, pode ter dados importantes, tentando download com FFMPEG: {name_lesson} ||| {lesson_video['url']} |||| {decryption_key}''', warning=True)
    return download_with_ffmpeg(decryption_key, name_lesson, lesson_video['url'])
    
  output = shorten_folder_name(concat_path(path, f'{index:03} - aula'))
  ydl_opts = ytdlp_options(output, session)
  return download_with_ytdlp(ydl_opts, lesson_video['url'])


def download_file(path, attachments):
  path = shorten_folder_name(path)
  if not os.path.exists(path):
    with open(path, 'wb') as file:
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
    attachments = requests.get(attachments_url, stream=True)
    path = concat_path(material_folder, clear_folder_name(attachment_name, is_file=True))
    download_file(path, attachments)
    logger(f'Conteúdo com DRM encontrado, pode ter dados importantes, download em: {path}', warning=True)


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
  download_with_ytdlp(ydl_opts, complementary)


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
