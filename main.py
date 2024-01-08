import json
from tqdm import tqdm
from download import download_attachments, download_video
from login import hotmartsession, selected_course, token, BeautifulSoup
from utils import clear_folder_name, concat_path, create_folder, shorten_folder_name


def extract_lessons_details(module_folder, lessons):
  lesson_detail = {}
  for i, lesson in enumerate(lessons, start=1):
    hashes = lesson['hash'] if isinstance(lesson['hash'], list) else [lesson['hash']]
    for hash in hashes:
      content_lesson = hotmartsession.get(f'https://api-club.cb.hotmart.com/rest/v3/page/{hash}?pageHash={hash}').json()
      lesson_title = f'{i:03d} - {clear_folder_name(content_lesson["name"])}'
      lesson_folder = create_folder(shorten_folder_name(concat_path(module_folder, lesson_title)))
      lesson_detail[content_lesson['name']] = {
        'path': lesson_folder, 
        'media': content_lesson.get('mediasSrc', []),
        'attachments': content_lesson.get('attachments', [])
      }
  
  return lesson_detail


def extract_modules_details(index, module_title, main_course_folder):
  module_folder =  create_folder(shorten_folder_name(concat_path(main_course_folder, f'{index:03d} - {clear_folder_name(module_title)}')))
  return module_folder


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
    urls = [asset.get('url') for asset in media_assets if 'url' in asset]
    return ', '.join([asset.get('url') for asset in media_assets if 'url' in asset])


def process_media(media, course_name):
  hotmartsession.headers['user-agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
  hotmartsession.headers['referer'] = f'https://{course_name}.club.hotmart.com/'
  lesson_video = hotmartsession.get(media['mediaSrcUrl'])

  return find_video(lesson_video)


def update_lessons_details(lessons, course_name):
  for lesson_info in lessons.values():
    lesson_media_links = [process_media(media, course_name) for media in lesson_info['media']]
    lesson_info['media'] = lesson_media_links
  download_video(lessons, hotmartsession)
  find_attachments(lessons, hotmartsession)

  return lessons


def list_modules(course_name, modules):
  main_course_folder = create_folder(clear_folder_name(course_name))

  for i, module in tqdm(enumerate(modules, start=1), total=len(modules), desc=course_name):
    module_folder = extract_modules_details(i, module['name'], main_course_folder)
    lessons = extract_lessons_details(module_folder, module['pages'])
    update_lessons_details(lessons, course_name)


def redirect_club_hotmart(course_name, course_link, access_token):
  hotmartsession.headers['authorization'] = f'Bearer {access_token}'
  hotmartsession.headers['club'] = course_name
  response = hotmartsession.get('https://api-club.cb.hotmart.com/rest/v3/navigation').json()
  modules = response['modules']
  list_modules(course_name, modules)


if __name__ == '__main__':
  course_name, course_link = selected_course
  redirect_club_hotmart(course_name, course_link, token)
