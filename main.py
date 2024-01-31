import json
from tqdm import tqdm
from threading import RLock
from connection import connect
from login import hotmartsession, course_name, token, BeautifulSoup
from utils import clear_folder_name, concat_path, create_folder, random_browser, logger, shorten_folder_name
from download import download_video


def extract_lessons_details(module_folder, lessons):
  lesson_detail = {}
  for i, lesson in enumerate(lessons, start=1):
    hashes = lesson['hash'] if isinstance(lesson['hash'], list) else [lesson['hash']]
    for hash in hashes:
      url = f'https://api-club.cb.hotmart.com/rest/v3/page/{hash}?pageHash={hash}'
      content_lesson = connect(url, hotmartsession).json()
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
        lesson_detail[lesson_name]['webinar'] = f'''https://api-live-admin.play.hotmart.com/v1/schedule/{lesson_detail[lesson_name]['content']}/private'''
        lesson_detail[lesson_name]['content'] = ''

  return lesson_detail


def extract_modules_details(index, module_title, main_course_folder):
  module_folder =  create_folder(shorten_folder_name(concat_path(main_course_folder, f'{index:03d} - {clear_folder_name(module_title)}')))
  return module_folder


def find_video(lesson_video):
  soup = BeautifulSoup(lesson_video.text, 'html.parser')
  script_tag = soup.find('script', {'id': '__NEXT_DATA__'})
  if script_tag:
    data = json.loads(script_tag.string)
    media_assets = data.get('props', {}).get('pageProps', {}).get('applicationData', {}).get('mediaAssets', [])
    return ', '.join([asset.get('url') for asset in media_assets if 'url' in asset])


def process_multiple_media(lesson_name, lesson_info):
  updated_lesson_info = {}
  for i, media in enumerate(lesson_info['media'], start=1):
    if lesson_info['media']:
      lesson_video = connect(lesson_info['media'][0]['mediaSrcUrl'], hotmartsession)
      lesson_video = find_video(lesson_video)
      part_lesson_name = f'{lesson_name} - Parte {i}'
      updated_lesson_info[part_lesson_name] = lesson_info.copy()
      updated_lesson_info[part_lesson_name]['media'] = [lesson_video]
  
  return updated_lesson_info


def process_media(lessons, course_name):
  updated_lessons = {}
  hotmartsession.headers['user-agent'] = random_browser()
  hotmartsession.headers['referer'] = f'https://{course_name}.club.hotmart.com/'

  for lesson_name, lesson_info in lessons.items():
    if len(lesson_info['media']) > 1:
      updated_lessons.update(process_multiple_media(lesson_name, lesson_info))
      continue
    
    updated_lessons[lesson_name] = lesson_info
    
    if lesson_info['media']:
      lesson_video = connect(lesson_info['media'][0]['mediaSrcUrl'], hotmartsession)
      lesson_video = find_video(lesson_video)
      updated_lessons[lesson_name]['media'] = [lesson_video]

  return updated_lessons


def process_lessons_details(lessons, course_name):
  processed_lessons = process_media(lessons, course_name)
  download_video(processed_lessons, hotmartsession)

  return processed_lessons


def process_module(module, main_course_folder, course_name):
  module_folder = extract_modules_details(module['index'], module['name'], main_course_folder)
  if module_folder:
    lessons = extract_lessons_details(module_folder, module['pages'])
    process_lessons_details(lessons, course_name)


def list_modules(course_name, modules):
    main_course_folder = create_folder(clear_folder_name(course_name))
    tqdm.set_lock(RLock())
    modules_data = [{'index': i, 'name': module['name'], 'pages': module['pages']} for i, module in enumerate(modules, start=1)]

    with tqdm(total=len(modules), desc=course_name, leave=True) as main_progress_bar:
        for module_data in modules_data:
            process_module(module_data, main_course_folder, course_name)
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
  redirect_club_hotmart(course_name, token)
