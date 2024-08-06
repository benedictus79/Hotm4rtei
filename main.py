import json
from tqdm import tqdm
from connection import connect
from concurrent.futures import ThreadPoolExecutor, as_completed
from login import hotmartsession, course_name, selected_folder, token, BeautifulSoup
from download import download_attachments, download_complementary, download_video, download_webinar, get_video_platform, process_complementary_readings, save_html
from utils import os, datetime, clear_folder_name, create_folder, logger, shorten_folder_name


def list_lessons(lessons):
  for path_module, lesson_data in lessons.items():
    lesson_detail = {}
    lesson_hash = lesson_data['lessons'][0]
    url = f"https://api-club.cb.hotmart.com/rest/v3/page/{lesson_hash}?pageHash={lesson_hash}"
    content_lesson = connect(url, hotmartsession).json()
    if content_lesson.get('error') == 'PAGE_LOCKED_CONTENT_DRIPPING':
      msg = f'Lição bloqueada do módulo: {path_module}'
      logger(msg, warning=True)
      continue
    lesson_title = f'{lesson_data["index"]:03d} - {clear_folder_name(content_lesson["name"])}'
    path_lesson = shorten_folder_name(os.path.join(path_module, lesson_title))
    lesson_name = clear_folder_name(content_lesson['name'])
    lesson_detail[path_lesson] = {
      'content': content_lesson.get('content', ''),
      'media': content_lesson.get('mediasSrc', []),
      'attachments': content_lesson.get('attachments', []),
      'complementary_readings': content_lesson.get('complementaryReadings', []),
    }
    if content_lesson.get('type') == 'WEBINAR':
      lesson_detail[lesson_name]['webinar'] = [f"https://api-live-admin.play.hotmart.com/v1/schedule/{lesson_detail[lesson_name]['content']}/private"]
      lesson_detail[lesson_name]['content'] = ''
    
    process_lessons(lesson_detail)


def find_webinar(path, webinars, hotmartsession):
  for i, webinar in enumerate(webinars):
    webinar_folder = create_folder(shorten_folder_name(os.path.join(path, 'webinar')))
    download_webinar(webinar_folder, i, webinar, hotmartsession)


def find_complementary_readings(path, complementary_readings):
  for i, complementary in enumerate(complementary_readings, start=1):
    complementary_url, complementary_name = complementary
    complementary_name = f'{i:03d} - {clear_folder_name(complementary_name)}'
    complementary_folder = create_folder(shorten_folder_name(os.path.join(path, 'extra')))
    process_complementary_readings(complementary_folder, complementary_url, complementary_name, hotmartsession)


def find_content(path, contents, session):
  for i, content in enumerate(contents, start=1):
    output_path = shorten_folder_name(os.path.join(path, f'{i:03d} - aula'))
    download_complementary(output_path, content, session)


def find_attachments(path, attachments):
  for i, attachment in enumerate(attachments, start=1):
    attachment_id, attachment_name = attachment
    attachment_name = f'{i:03d} - {attachment_name}'
    material_folder = create_folder(shorten_folder_name(os.path.join(path, 'material')))
    download_attachments(material_folder, attachment_id, attachment_name, hotmartsession)


def process_media(lesson_path, media):
  if media:
    videos_urls = [item['mediaSrcUrl'] for item in media]
    lesson_path = create_folder(lesson_path)
    process_media_download(lesson_path, videos_urls)


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


def process_attachments(path_lesson, attachments):
  if attachments:
    attachments_data = [(item['fileMembershipId'], item['fileName']) for item in attachments]
    path_lesson = create_folder(path_lesson)
    find_attachments(path_lesson, attachments_data)


def process_webinar(lesson_path, webinar):
  if webinar:
    lesson_path = create_folder(lesson_path)
    find_webinar(lesson_path, webinar, hotmartsession)


def process_readings(lesson_path, readings):
  if readings:
    readings_data = [(item['articleUrl'], item['articleName']) for item in readings]
    lesson_path = create_folder(lesson_path)
    find_complementary_readings(lesson_path, readings_data)


def process_content(lesson_path, content):
  if content:
    soup = BeautifulSoup(content, 'html.parser')
    iframe = soup.find('iframe')
    process_iframe(soup, lesson_path, iframe)


def process_iframe(soup, path, iframe):
  if iframe:
    video_url = get_video_platform(iframe)
    find_content(path, video_url, hotmartsession)
  else:
    path = create_folder(path)
    content_folder = create_folder(shorten_folder_name(os.path.join(path, 'html')))
    save_html(content_folder, soup)


def process_lessons(lesson):
  for path, data in lesson.items():
    process_media(path, data.get('media'))
    process_attachments(path, data.get('attachments'))
    process_webinar(path, data.get('webinar'))
    process_readings(path, data.get('complementary_readings'))
    process_content(path, data.get('content'))


def extract_lessons_details(path, lessons):
  with ThreadPoolExecutor(max_workers=3) as executor:
    futures = []
    for i, lesson in enumerate(lessons, start=1):
      data_lesson = {}
      hashes = lesson['hash'] if isinstance(lesson['hash'], list) else [lesson['hash']]
      path_module = create_folder(path)
      data_lesson[path_module] = {'index': i, 'lessons': hashes}
      future = executor.submit(list_lessons, data_lesson)
      futures.append(future)
    for future in as_completed(futures):
      future.result()


def process_module(main_course_folder, data):
  for module_title, module_data in data.items():
    path_module =  create_folder(shorten_folder_name(os.path.join(main_course_folder, module_title)))
    extract_lessons_details(path_module, module_data)


def list_modules(selected_folder, course_name, modules):
  if selected_folder == '' or not os.path.exists(selected_folder):
    selected_folder = os.getcwd()
  main_course_folder = create_folder(os.path.join(selected_folder, clear_folder_name(course_name)))
  for i, module in enumerate(tqdm(modules, desc='Processing Modules', total=len(modules)), start=1):
    data_module = {}
    module_title = f'{i:03d} - {clear_folder_name(module["name"])}'
    data_module[module_title] = module['pages']
    process_module(main_course_folder, data_module)


def redirect_club_hotmart(selected_folder, course_name, access_token):
  hotmartsession.headers['authorization'] = f'Bearer {access_token}'
  hotmartsession.headers['club'] = course_name
  hotmartsession.headers['referer'] = f'https://{course_name}.club.hotmart.com/'
  response = hotmartsession.get('https://api-club.cb.hotmart.com/rest/v3/navigation')
  response = response.json()
  modules = response['modules']
  filtered_modules = [module for module in modules if not module['locked']]
  modules_locked_names = [module['name'] for module in modules if module['locked']]
  if modules_locked_names:
    msg_erro = f'Curso: {course_name} - Modulos Bloqueados: {modules_locked_names}'
    logger(msg_erro, warning=True)
  list_modules(selected_folder, course_name, filtered_modules)


if __name__ == '__main__':
  start_time = datetime.now()
  print(f'Início da execução: {start_time.strftime("%Y-%m-%d %H:%M:%S")}')
  redirect_club_hotmart(selected_folder, course_name, token)
  end_time = datetime.now()
  print(f'Fim da execução: {end_time.strftime("%Y-%m-%d %H:%M:%S")}')
  input("Pressione Enter para fechar...")