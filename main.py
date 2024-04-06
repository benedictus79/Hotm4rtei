from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
import json
import threading
from tqdm import tqdm
from threading import RLock
from connection import connect
from login import hotmartsession, course_name, token, BeautifulSoup
from utils import clear_folder_name, concat_path, create_folder, logger, shorten_folder_name
from download import download_attachments, download_complementary, download_video, is_pandavideo_iframe, is_vimeo_iframe, process_complementary_readings, process_webinar, save_html, url_conveter_pandavideo, pandavideoheaders
import datetime


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
    output_path = shorten_folder_name(concat_path(path, f'{i:03d} - aula.mp4'))
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
    media_assets = data.get('props', {}).get('pageProps', {}).get('applicationData', {}).get('mediaAssets', [])
    urls = [asset.get('url') for asset in media_assets if 'url' in asset]
    return urls[0]


def process_media(path, medias):
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
  content_folder = create_folder(shorten_folder_name(concat_path(path, 'html')))
  save_html(content_folder, soup)


def process_data(lessons, course_name):
  hotmartsession.headers['referer'] = f'https://{course_name}.club.hotmart.com/'

  for lesson_name, lesson_info in lessons.items():
    if lesson_info['media']:
      videos_urls = [item['mediaSrcUrl'] for item in lesson_info['media']]
      process_media(lesson_info['path'], videos_urls)
    if lesson_info['attachments']:
      attachments_data = [(item['fileMembershipId'], item['fileName']) for item in lesson_info['attachments']]
      find_attachments(lesson_info['path'], attachments_data)
    if lesson_info.get('webinar'):
      find_webinar(lesson_info['path'], lesson_info['webinar'], hotmartsession)
    if lesson_info['complementary_readings']:
      complementary_readings_data = [(item['articleUrl'], item['articleName']) for item in lesson_info['complementary_readings']]
      find_complementary_readings(lesson_info['path'], complementary_readings_data) 
    if lesson_info.get('content'):
      soup = BeautifulSoup(lesson_info['content'], 'html.parser')
      iframe = soup.find('iframe')
      process_iframe(soup, lesson_info['path'], iframe)


def process_lessons_details(lessons, course_name):
  processed_lessons = process_data(lessons, course_name)
  return processed_lessons


def process_module(module, main_course_folder, course_name):
  module_folder = extract_modules_details(module['index'], module['name'], main_course_folder)
  if module_folder:
    lessons = extract_lessons_details(module_folder, module['pages'])
    process_lessons_details(lessons, course_name)


def process_and_update(module_data, main_course_folder, course_name):
  process_module(module_data, main_course_folder, course_name)


def list_modules(course_name, modules):
  main_course_folder = create_folder(clear_folder_name(course_name))
  lock = threading.RLock()
  tqdm.set_lock(RLock())

  modules_data = [{'index': i, 'name': module['name'], 'pages': module['pages']} for i, module in enumerate(modules, start=1)]

  with ThreadPoolExecutor(max_workers=3, initializer=tqdm.set_lock, initargs=(lock,)) as executor:
    future_to_module = [executor.submit(process_module, module_data, main_course_folder, course_name) for module_data in modules_data]
    main_progress_bar = tqdm(total=len(future_to_module), desc=course_name, leave=True)
    for future in as_completed(future_to_module):
      _ = future.result()
      main_progress_bar.update(1)


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
  start_time = datetime.datetime.now()
  print(f"Início da execução: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
  redirect_club_hotmart(course_name, token)
  end_time = datetime.datetime.now()
  print(f"Fim da execução: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
