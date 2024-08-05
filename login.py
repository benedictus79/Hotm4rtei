import requests
from bs4 import BeautifulSoup
from utils import os, benedictus_ascii_art, clear_screen, logger


hotmartsession = requests.Session()


def credentials():
  benedictus_ascii_art()
  username = input('email: ')
  password = input('senha: ')
  clear_screen()
  return username, password


def get_token(url_token, username, password):
  files = {
    'grant_type': (None, 'password'),
    'username': (None, username),
    'password': (None, password)
  }
  response = hotmartsession.post(url_token, files=files)

  if response.status_code != 200:
    msg_erro = f'Erro ao acessar {response.url}: Status Code {response.status_code}'
    logger(msg_erro, error=True)
    return None

  return response.json()['access_token']


def check_token(access_token):
  params = {'token': access_token}
  url_check_token = 'https://sec-proxy-content-distribution.hotmart.com/club/security/oauth/check_token'
  response = hotmartsession.get(url_check_token, params=params)
  if response.status_code != 200:
    msg_erro = f'Erro ao acessar {response.url}: Status Code {response.status_code}'
    logger(msg_erro, error=True)
    return None
  response = response.json()['resources']
  courses = {}

  for resource in response:
    resource_info = resource.get('resource', {})
    if resource_info.get('status') == 'ACTIVE' or resource_info.get('status') == 'OVERDUE':
      courses[resource_info['subdomain']] = f'''https://{resource_info['subdomain']}.club.hotmart.com'''

  return courses


def choose_course(courses):
  print('Courses:')
  if courses is None:return None, None
  for i, course_title in enumerate(courses.keys(), start=1):
    print(f'{i}. {course_title}')

  choice = input('Choose a course by number: ')
  if not choice.isdigit():return None, None
  selected_course_title = list(courses.keys())[int(choice) - 1]
  selected_course_link = courses[selected_course_title]
  print(f'Selected course link:', selected_course_link)
  print(f'The folder size may cause errors due to excessively long directories.')
  print(f'If you do not specify anything or if the folder does not exist, the download will be done in the folder: {os.getcwd()}.')
  selected_course_folder = input(f'Choose the folder for download: ').strip()
  
  return selected_course_title, selected_course_link, selected_course_folder

username, password = credentials()
url_token = 'https://sec-proxy-content-distribution.hotmart.com/club/security/oauth/token'
token = get_token(url_token, username, password)
courses = check_token(token)
course_name, course_link, selected_folder = choose_course(courses)
