import requests
from bs4 import BeautifulSoup
from utils import benedictus_ascii_art, clear_screen, logger


hotmartsession = requests.Session()


def get_token():
  url_token = 'https://sec-proxy-content-distribution.hotmart.com/club/security/oauth/token'
  benedictus_ascii_art()
  username = input('email: ')
  password = input('senha: ')
  clear_screen()
  data = {
    'grant_type': 'password',
    'username': username,
    'password': password
  }
  response = hotmartsession.post(url_token, data=data)

  if response.status_code != 200:
    msg_erro = f'Erro ao acessar {response.url}: Status Code {response.status_code}'
    logger(msg_erro, error=True)
    return

  return response.json()['access_token']


def check_token(access_token):
  params = {
    'token': access_token
  }
  url_check_token = 'https://sec-proxy-content-distribution.hotmart.com/club/security/oauth/check_token'
  response = hotmartsession.get(url_check_token, params=params)
  response = response.json()['resources']
  courses = {}

  for resource in response:
    resource_info = resource.get('resource', {})
    if resource_info.get('status') == 'ACTIVE':
      courses[resource_info['subdomain']] = f'''https://{resource_info['subdomain']}.club.hotmart.com'''

  return courses


def choose_course(courses):
  print('Cursos disponíveis:')
  for i, (course_title, course_info) in enumerate(courses.items(), start=1):
    print(f'{i}. {course_title}')

  choice = input('Escolha um curso pelo número: ')
  selected_course_title = list(courses.keys())[int(choice) - 1]
  selected_course_link = courses[selected_course_title]
  
  return selected_course_title, selected_course_link


token = get_token()
courses = check_token(token)
selected_course = choose_course(courses)
