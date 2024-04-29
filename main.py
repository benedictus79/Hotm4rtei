from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import threading
from tqdm import tqdm
from connection import connect
from login import hotmartsession, course_name, token, BeautifulSoup
from utils import datetime, clear_folder_name, concat_path, create_folder, logger, shorten_folder_name
from download import download_attachments, download_complementary, download_video, is_pandavideo_iframe, is_vimeo_iframe, process_complementary_readings, process_webinar, save_html, url_conveter_pandavideo, pandavideoheaders


def extract_lessons_details(module_folder, lessons):
  lesson_detail = {}
  for i, lesson in enumerate(lessons, start=1):
    hashes = lesson['hash'] if isinstance(lesson['hash'], list) else [lesson['hash']]
    for hash in hashes:
      url = f'https://api-club.cb.hotmart.com/rest/v3/page/{hash}?pageHash={hash}'
      content_lesson = connect(url, hotmartsession).json()
      if content_lesson.get('error') == 'PAGE_LOCKED_CONTENT_DRIPPING':
        msg = f'Lição bloqueada do módulo: {module_folder}'
        logger(msg, warning=True)
        continue
      lesson_title = f'''{i:03d} - {clear_folder_name(content_lesson['name'])}'''
      lesson_folder = create_folder(shorten_folder_name(concat_path(module_folder, lesson_title)))
      lesson_name = clear_folder_name(content_lesson['name'])
      lesson_detail[lesson_name] = {
        'path': lesson_folder,
        'content': content_lesson.get('content', ''),
        'media': content_lesson.get('mediasSrc', []),
        'attachments': content_lesson.get('attachments', []),
        'complementary_readings': content_lesson.get('complementaryReadings', []),
      }
      if content_lesson.get('type') == 'WEBINAR':
        lesson_detail[lesson_name]['webinar'] = [f'''https://api-live-admin.play.hotmart.com/v1/schedule/{lesson_detail[lesson_name]['content']}/private''']
        lesson_detail[lesson_name]['content'] = ''
  
  return lesson_detail


def extract_modules_details(index, module_title, main_course_folder):
  module_folder =  create_folder(shorten_folder_name(concat_path(main_course_folder, f'{index:03d} - {clear_folder_name(module_title)}')))
  return module_folder


def find_webinar(path, webinars, hotmartsession):
  for i, webinar in enumerate(webinars):
    webinar_folder = create_folder(shorten_folder_name(concat_path(path, 'webinar')))
    process_webinar(webinar_folder, i, webinar, hotmartsession)


def find_complementary_readings(path, complementary_readings):
  for i, complementary in enumerate(complementary_readings, start=1):
    complementary_url, complementary_name = complementary
    complementary_name = f'{i:03d} - {complementary_name}'
    complementary_folder = create_folder(shorten_folder_name(concat_path(path, 'complemento')))
    process_complementary_readings(complementary_folder, complementary_url, complementary_name, hotmartsession)


def find_content(path, contents, session):
  for i, content in enumerate(contents, start=1):
    output_path = shorten_folder_name(concat_path(path, f'{i:03d} - aula'))
    download_complementary(output_path, content, session)


def find_attachments(path, attachments):
  for i, attachment in enumerate(attachments, start=1):
    attachment_id, attachment_name = attachment
    attachment_name = f'{i:03d} - {attachment_name}'
    material_folder = create_folder(shorten_folder_name(concat_path(path, 'material')))
    download_attachments(material_folder, attachment_id, attachment_name, hotmartsession)


def find_video(lesson_video):
  soup = BeautifulSoup(lesson_video.text, 'html.parser')
  script_tag = soup.find('script', {'id': '__NEXT_DATA__'})
  if script_tag:
    data = json.loads(script_tag.string)
    application_data = data.get('props', {}).get('pageProps', {}).get('applicationData', {})
    media_assets = application_data.get('mediaAssets', [])
    drm_urls = [asset.get('url') for asset in media_assets if 'url' in asset and '/drm/' in asset.get('url')]
    preferred_url = next((url for url in drm_urls if '.mpd' in url), None)
    if not preferred_url:
      preferred_url = [asset.get('url') for asset in media_assets if 'url' in asset]
      preferred_url = preferred_url[0]
    preferred_url = preferred_url if preferred_url else ''
    signature = application_data.get('signature', '')
    mediaCode = application_data.get('mediaCode', '')
    userCode = application_data.get('userCode', '')
    applicationKey = application_data.get('applicationKey', '')
    clubMembershipId = application_data.get('clubMembershipId', '')
    
    return_data = {
      'url': preferred_url,
      'signature': signature,
      'mediaCode': mediaCode,
      'userCode': userCode,
      'applicationKey': applicationKey,
      'clubMembershipId': clubMembershipId,
    }
    return return_data


def process_media_download(path, medias):
  for i, media in enumerate(medias, start=1):
    lesson_video = connect(media, hotmartsession)
    lesson_video = find_video(lesson_video)
    download_video(path, i, lesson_video, hotmartsession)


def process_iframe(soup, path, iframe):
  if iframe and is_vimeo_iframe(iframe):
    video_url = [iframe['src']]
    find_content(path, video_url, hotmartsession)
  elif iframe and is_pandavideo_iframe(iframe):
    video_url = [url_conveter_pandavideo(iframe['src'])]
    hotmartsession.headers.update(pandavideoheaders(iframe['src']))
    find_content(path, video_url, hotmartsession)
  else:
    content_folder = create_folder(shorten_folder_name(concat_path(path, 'html')))
    save_html(content_folder, soup)


def process_media(lesson_path, media):
  videos_urls = [item['mediaSrcUrl'] for item in media]
  process_media_download(lesson_path, videos_urls)


def process_attachments(lesson_path, attachments):
  attachments_data = [(item['fileMembershipId'], item['fileName']) for item in attachments]
  find_attachments(lesson_path, attachments_data)


def process_webinar(lesson_path, webinar):
  find_webinar(lesson_path, webinar)


def process_readings(lesson_path, readings):
  readings_data = [(item['articleUrl'], item['articleName']) for item in readings]
  find_complementary_readings(lesson_path, readings_data, hotmartsession)


def process_content(lesson_path, content):
  soup = BeautifulSoup(content, 'html.parser')
  iframe = soup.find('iframe')
  process_iframe(soup, lesson_path, iframe)


def process_lesson(lesson_name, lesson_info):
  task_mapping = {
    'media': (process_media, lesson_info.get('path'), lesson_info.get('media')),
    'attachments': (process_attachments, lesson_info.get('path'), lesson_info.get('attachments')),
    'webinar': (process_webinar, lesson_info.get('path'), lesson_info.get('webinar')),
    'complementary_readings': (process_readings, lesson_info.get('path'), lesson_info.get('complementary_readings'), hotmartsession),
    'content': (process_content, lesson_info.get('path'), lesson_info.get('content'))
  }

  with ThreadPoolExecutor(max_workers=5) as executor:
    futures = []
    for key, (func, *args) in task_mapping.items():
      if lesson_info.get(key):
        future = executor.submit(func, *args)
        futures.append(future)
    for future in futures:
      future.result()


def process_lessons_details(lessons, course_name):
  hotmartsession.headers['referer'] = f'https://{course_name}.club.hotmart.com/'
  with ThreadPoolExecutor(max_workers=3) as executor:
    for lesson_name, lesson_info in lessons.items():
      executor.submit(process_lesson, lesson_name, lesson_info)


def process_module(module_data, main_course_folder, course_name):
  try:
    module_folder = extract_modules_details(module_data['index'], module_data['name'], main_course_folder)
    if module_folder:
      lessons = extract_lessons_details(module_folder, module_data['pages'])
      process_lessons_details(lessons, course_name)
  except Exception as e:
    msg = f"Erro ao processar módulo, verifique manualmente: {str(module_folder)} ||| {e}"
    return logger(msg, error=True)


def list_modules(course_name, modules):
  main_course_folder = create_folder(clear_folder_name(course_name))
  lock = threading.RLock()
  tqdm.set_lock(lock)
  modules_data = [{'index': i, 'name': module['name'], 'pages': module['pages']} for i, module in enumerate(modules, start=1)]
  
  with ThreadPoolExecutor(max_workers=3) as executor:
    futures = [executor.submit(process_module, module_data, main_course_folder, course_name) for module_data in modules_data]
    for future in tqdm(as_completed(futures), total=len(futures), desc=course_name, leave=True):
      future.result()


def redirect_club_hotmart(course_name, access_token):
  hotmartsession.headers['authorization'] = f'Bearer {access_token}'
  hotmartsession.headers['club'] = course_name
  response = hotmartsession.get('https://api-club.cb.hotmart.com/rest/v3/navigation')
  if response.status_code != 200: return print('Bye bye...')
  response = response.json()
  modules = response['modules']
  filtered_modules = [module for module in modules if not module['locked']]
  modules_locked_names = [module['name'] for module in modules if module['locked']]
  if modules_locked_names:
    msg_erro = f'Curso: {course_name} - Modulos Bloqueados: {modules_locked_names}'
    logger(msg_erro, warning=True)
  list_modules(course_name, filtered_modules)


if __name__ == '__main__':
  start_time = datetime.now()
  print(f'Início da execução: {start_time.strftime("%Y-%m-%d %H:%M:%S")}')
  redirect_club_hotmart(course_name, token)
  end_time = datetime.now()
  print(f'Fim da execução: {end_time.strftime("%Y-%m-%d %H:%M:%S")}')
  input("Pressione Enter para fechar...")
