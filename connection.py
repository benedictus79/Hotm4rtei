from login import requests, url_token, username, password, course_name, course_link
from utils import logger, random_sleep


def refresh_token(url_token=url_token, username=username, password=password):
  data = {
    'grant_type': 'password',
    'username': username,
    'password': password
  }
  hotmart_new_session = requests.Session()
  response = hotmart_new_session.post(url_token, data=data)

  if response.status_code != 200:
    msg_erro = f'Erro ao acessar {response.url}: Status Code {response.status_code}'
    logger(msg_erro, error=True)
    return None
  
  access_token = response.json()['access_token']
  hotmart_new_session.headers['club'] = course_name
  hotmart_new_session.headers['referer'] = course_link
  hotmart_new_session.headers.update({'Authorization': f'Bearer {access_token}'})

  return hotmart_new_session


def connect(url, session):
  try:
    return session.get(url)
  except requests.exceptions.ConnectionError as e:
    random_sleep()
    logger(f'Possivelmente seu token expirou, tentando novamente: {e}', warning=True)
    new_session = refresh_token(url_token)
    return new_session.get(url)


def check_forbidden(ydl_opts, media, session):
  new_session = connect(media, session)
  ydl_opts['http_headers'] = new_session
  
  return ydl_opts
