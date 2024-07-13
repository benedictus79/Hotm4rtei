import subprocess
import yt_dlp
from connection import connect, connect_license_drm
from login import requests, hotmartsession, BeautifulSoup
from utils import SilentLogger, clear_folder_name, logger, os, re, shorten_folder_name


def ytdlp_options(output_folder, session=None):
  options = {
    'logger': SilentLogger(),
    'merge_output_format': 'mp4',
    'format': 'bestvideo+bestaudio/best',
    'outtmpl': f'{output_folder}.%(ext)s',
    'quiet': True,
    'continuedl': True,
    'no_progress': True,
    'no_overwrites': True,
    'windows_filenames': True,
    'retries': 50,
    'trim_file_name': 249,
    'fragment_retries': 50,
    'extractor_retries': 50,
    'file_access_retries': 50,
    'concurrent_fragment_downloads': 10,
  }
  if session:
    options['http_headers'] = {'referer': session.headers['referer'], 'Upgrade-Insecure-Requests': '1'}
  
  return options


def download_with_ffmpeg(decryption_key, name_lesson, url):
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
  result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  if result.returncode != 0:
    error_message = f'Erro ao baixar a aula {name_lesson}: {result.stderr.decode()}'
    logger(error_message, error=True)

  return result


def download_with_ytdlp(ydl_opts, media):
  while True:
    try:
      with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([media])
        return
    except yt_dlp.utils.DownloadError as e:
      msg = f"Verifique manualmente, se não baixou tente novamente mais tarde: {ydl_opts['outtmpl']} ||| {media} ||| {e}"
      logger(msg, warning=True)
      return


def get_video_platform(iframe):
  if iframe is not None and 'src' in iframe.attrs:
    src_url = iframe['src']
    if 'vimeo' in src_url:
      return [src_url]
    elif 'pandavideo' in src_url:
      src_url = [url_conveter_pandavideo(iframe['src'])]
      hotmartsession.headers.update(pandavideoheaders(iframe['src']))
      return [src_url]
    elif 'you' in src_url:
      src_url = complete_youtube_url(iframe['src'])
      return [src_url]


def url_conveter_pandavideo(url):
  pattern = r'https://player-vz-([a-zA-Z0-9-]+).tv.pandavideo.com.br/embed/\?v=([a-zA-Z0-9-]+)'
  match = re.search(pattern, url)
  if match:
    subdomain = match.group(1)
    extracted_part = match.group(2)
    video_url = f'https://b-vz-{subdomain}.tv.pandavideo.com.br/{extracted_part}/playlist.m3u8'
    return video_url


pandavideoheaders = lambda rerefer: {
  'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Referer': rerefer,
}

def complete_youtube_url(url):
  if not url.startswith("http"):
    url = "https:" + url
  return url


def save_html(content_folder, html):
  file_path = shorten_folder_name(os.path.join(content_folder, 'texto.html'))
  if not os.path.exists(file_path):
    with open(file_path, 'w', encoding='utf-8') as file:
      file.write(str(html))


def save_link(complementary_folder, complementary_url, complementarys_name):
  file_path = shorten_folder_name(os.path.join(complementary_folder, f'{complementarys_name}.txt'))
  if not os.path.exists(file_path):
    with open(file_path, 'w', encoding='utf-8') as file:
      file.write(str(complementary_url))


def download_file(path, attachments, drm=None):
  path = shorten_folder_name(path)
  if not os.path.exists(path):
    if drm:logger(f'Conteúdo com DRM encontrado, pode ter dados importantes, download em: {path}', warning=True)
    with open(path, 'wb') as file:
      for chunk in attachments.iter_content(chunk_size=8192):
        file.write(chunk)


def download_attachments(material_folder, attachment_id, attachment_name, session):
  response = session.get(f'https://api-club.cb.hotmart.com/rest/v3/attachment/{attachment_id}/download?attachmentId={attachment_id}').json()
  if response.get('directDownloadUrl'):
    attachments_url = response['directDownloadUrl']
    attachments = requests.get(attachments_url, stream=True)
    path = os.path.join(material_folder, clear_folder_name(attachment_name))
    download_file(path, attachments)
  elif response.get('lambdaUrl'):
    session.headers['authority'] = 'drm-protection.cb.hotmart.com'
    session.headers['token'] = response.get('token')
    attachments_url = connect('https://drm-protection.cb.hotmart.com', session).text
    attachments = requests.get(attachments_url, stream=True)
    path = os.path.join(material_folder, clear_folder_name(attachment_name))
    download_file(path, attachments, drm=True)


def download_complementary(complementary_folder, complementary, session=None):
  ydl_opts = ytdlp_options(complementary_folder)
  if session:
    ydl_opts = ytdlp_options(complementary_folder, session)
  download_with_ytdlp(ydl_opts, complementary)


def process_complementary_readings(complementary_folder, complementary_url, complementarys_name, session):
  if 'youtube' in complementary_url or 'youtu.be' in complementary_url:
    new_complementary_folder = shorten_folder_name(os.path.join(complementary_folder, f'{complementarys_name}'))
    return download_complementary(new_complementary_folder, complementary_url)
  elif complementary_url:
    return save_link(complementary_folder, complementary_url, complementarys_name)


def download_webinar(webinar_folder, index, webinar, session):
  response = connect(webinar, session)
  response = session.get(webinar).json()
  webinar_link, webinar_title = response['url'], response['name']
  webinar_folder = os.path.join(webinar_folder, f'{index:03d} - {webinar_title}')
  return download_complementary(webinar_folder, webinar_link)


def download_attachments(material_folder, attachment_id, attachment_name, session):
  response = session.get(f'https://api-club.cb.hotmart.com/rest/v3/attachment/{attachment_id}/download?attachmentId={attachment_id}').json()
  if response.get('directDownloadUrl'):
    attachments_url = response['directDownloadUrl']
    attachments = requests.get(attachments_url, stream=True)
    path = os.path.join(material_folder, clear_folder_name(attachment_name))
    download_file(path, attachments)
  elif response.get('lambdaUrl'):
    session.headers['authority'] = 'drm-protection.cb.hotmart.com'
    session.headers['token'] = response.get('token')
    attachments_url = connect('https://drm-protection.cb.hotmart.com', session).text
    attachments = requests.get(attachments_url, stream=True)
    path = os.path.join(material_folder, clear_folder_name(attachment_name))
    download_file(path, attachments, drm=True)


def get_pssh(response):
  soup = BeautifulSoup(response.text, 'xml')
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
  api_url = 'https://cdrm-project.com/'
  license_url = data['license']
  pssh = data['pssh']
  json_data = {
    'PSSH': pssh,
    'License URL': license_url,
    'Headers': "{\n'accept': '*/*',\n'accept-language': 'pt-BR,pt;q=0.7',\n'cache-control': 'no-cache',\n'content-type': 'application/octet-stream',\n'keysystem': 'com.widevine.alpha',\n'origin': 'https://cf-embed.play.hotmart.com',\n'pragma': 'no-cache',\n'priority': 'u=1, i',\n'referer': 'https://cf-embed.play.hotmart.com/',\n'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',\n}",
    'JSON': '',
    'Cookies': '',
    'Data': '',
    'Proxy': '',
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
  decryption_results = requests.post(api_url, json=json_data, headers=headers, timeout=80)
  decryption_key = decryption_results.json()['Message'].split(':')[1].strip()
  return decryption_key


def download_video(path, index, lesson_video, session):
  if 'drm/' in lesson_video['url']:
    response = connect(lesson_video['url'], session)
    pssh = get_pssh(response)
    license_url = get_license(lesson_video, session)
    wv_data = {
      'license': license_url,
      'pssh': pssh
    }
    decryption_key = get_key_drm(wv_data)
    name_lesson = shorten_folder_name(os.path.join(path, f' {index:03} - aula'))
    logger(f'''Conteúdo com DRM encontrado, pode ter dados importantes, tentando download com FFMPEG: {name_lesson} ||| {lesson_video['url']} |||| {decryption_key}''', warning=True)
    if not (os.path.exists(f'{name_lesson}.mp4')):
      return download_with_ffmpeg(decryption_key, name_lesson, lesson_video['url'])
  output = shorten_folder_name(os.path.join(path, f'{index:03} - aula'))
  ydl_opts = ytdlp_options(output)
  ydl_opts['http_headers'] = {'referer': 'https://cf-embed.play.hotmart.com/'}
  return download_with_ytdlp(ydl_opts, lesson_video['url'])
