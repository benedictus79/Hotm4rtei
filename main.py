import json
from tqdm import tqdm
from threading import RLock
from functools import partial
from concurrent.futures import ThreadPoolExecutor
from connection import connect
from login import hotmartsession, course_name, course_link, token, BeautifulSoup
from utils import clear_folder_name, concat_path, create_folder, random_browser, logger, shorten_folder_name
from download import download_attachments, download_complementary, download_video, is_pandavideo_iframe, is_vimeo_iframe, save_html, save_link, url_conveter_pandavideo, pandavideoheaders


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


def process_complementary_readings(complementary_folder, complementarys, session):
  for i, complementary in enumerate(complementarys, start=1):
    article_url = complementary.get('articleUrl')
    if article_url and ('youtube' in article_url or 'youtu.be' in article_url):
      complementary_title = clear_folder_name(complementary.get('articleName'))
      new_complementary_folder = shorten_folder_name(concat_path(complementary_folder, f'{i:03d} - {complementary_title}.mp4'))
      download_complementary(new_complementary_folder, article_url)
    elif article_url:
      save_link(complementary_folder, i, article_url)


def process_webinar(webinar_folder, index, webinar, session):
  response = connect(webinar, session)
  response = session.get(webinar).json()
  webinar_link, webinar_title = response['url'], response['name']
  webinar_folder = concat_path(webinar_folder, f'{index:03d} - {webinar_title}.mp4')
  download_complementary(webinar_folder, webinar_link)


def find_webinar(lessons, session):
  for i, (lesson_name, lesson_data) in enumerate(lessons.items(), start=1):
    if lesson_data.get('webinar'):
      webinar_folder = create_folder(shorten_folder_name(concat_path(lesson_data['path'], 'webinar')))
      process_webinar(webinar_folder, i, lesson_data['webinar'], session)


def find_complementary_readings(lessons, session):
  for lesson_name, lesson_data in lessons.items():
    if lesson_data.get('complementary_readings'):
      complementary_folder = create_folder(shorten_folder_name(concat_path(lesson_data['path'], 'complemento')))
      process_complementary_readings(complementary_folder, lesson_data['complementary_readings'], session)


def find_content(lessons, session):
  for lesson_name, lesson_data in lessons.items():
    if lesson_data['content']:
      soup = BeautifulSoup(lesson_data['content'], 'html.parser')
      iframe = soup.find('iframe')
      if iframe and is_vimeo_iframe(iframe):
        video_url = iframe['src']
        output_path = shorten_folder_name(concat_path(lesson_data['path'], f'{lesson_name}.mp4'))
        session.headers['Referer'] = course_link
        download_complementary(output_path, video_url, session)
      if iframe and is_pandavideo_iframe(iframe):
        video_url = url_conveter_pandavideo(iframe['src'])
        output_path = shorten_folder_name(concat_path(lesson_data['path'], f'{lesson_name}.mp4'))
        session.headers.update(pandavideoheaders(iframe['src']))
        download_complementary(output_path, video_url, session)
      content_folder = create_folder(shorten_folder_name(concat_path(lesson_data['path'], 'html')))
      save_html(content_folder, lesson_data['content'])


def find_attachments(lessons, session):
  for lesson_name, lesson_data in lessons.items():
    if lesson_data['attachments']:
      material_folder = create_folder(shorten_folder_name(concat_path(lesson_data['path'], 'material')))
      download_attachments(material_folder, lesson_data['attachments'], session)


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
  find_webinar(processed_lessons, hotmartsession)
  find_complementary_readings(processed_lessons, hotmartsession)
  find_attachments(processed_lessons, hotmartsession)
  find_content(processed_lessons, hotmartsession)

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
  partial_functions = [partial(process_module, module_data, main_course_folder, course_name) for module_data in modules_data]

  with ThreadPoolExecutor(max_workers=2, initializer=tqdm.set_lock, initargs=(tqdm.get_lock(),)) as executor:
    main_progress_bar = tqdm(total=len(modules), desc=course_name, leave=True)
    for _ in executor.map(lambda f: f(), partial_functions):
      main_progress_bar.update(1)
    main_progress_bar.close()


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
