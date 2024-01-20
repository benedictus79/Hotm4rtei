import os
import re
import random
from datetime import datetime
from time import sleep



def benedictus_ascii_art():
  benedictus = """
     ___ ___ _  _ ___ ___ ___ ___ _____ _   _ ___ 
    | _ ) __| \| | __|   \_ _/ __|_   _| | | / __|
    | _ \ _|| .` | _|| |) | | (__  | | | |_| \__ \\
    |___/___|_|\_|___|___/___\___| |_|  \___/|___/
    
  Author: Benedictus ©
  Community: https://t.me/alex4ndriagroup
  Script: {name}
  Version: {version}
  """
  print(benedictus.format(name='hotm4rtei', version='Alpha 0.8.1'))


def clear_screen():
  os.system('cls || clear')


def create_folder(folder_name):
  path = os.path.join(os.getcwd(), folder_name)

  if not os.path.exists(path):
    os.mkdir(path)

  return path


def clear_folder_name(name):
  sanitized_name = re.sub(r'[<>:"/\\|?*]', ' ', name)
  sanitized_name = re.sub(r'\s+', ' ', sanitized_name).strip()
  sanitized_name = re.sub(r'\.$', '', sanitized_name)

  return sanitized_name


def shorten_folder_name(full_path, max_length=210):
  if len(full_path) > max_length:
    num_chars_to_remove = len(full_path) - max_length
    directory, file_name = os.path.split(full_path)
    base_name, extension = os.path.splitext(file_name)
    num_chars_to_remove = min(num_chars_to_remove, len(base_name))
    shortened_name = base_name[:-num_chars_to_remove] + extension
    new_full_path = os.path.join(directory, shortened_name)
    return new_full_path
    
  return full_path


def concat_path(path, subpath, lesson=None):
  fullpath = os.path.join(path, subpath)

  if lesson:
    fullpath = os.path.join(path, subpath, lesson)

  return fullpath


def log_to_file(filename, message):
  timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
  with open(filename, 'a', encoding='UTF-8') as file:
    file.write(f'{timestamp} - {message}\n')


def logger(message, error=None, warning=None):
  if error:
    log_to_file('hotm4rtei_erros.txt', message)
  if warning:
    log_to_file('hotm4rtei_avisos.txt', message)


def random_sleep():
  sleep(random.randint(45, 70))


def random_browser():
  user_agents = {
    'Windows': [
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:88.0) Gecko/20100101 Firefox/88.0',
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36 Edg/90.0.818.66'
    ],
    'Linux': [
      'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
      'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0'
    ],
    'macOS': [
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:88.0) Gecko/20100101 Firefox/88.0',
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1 Safari/605.1.15'
    ]
  }

  return random.choice(random.choice(list(user_agents.values())))


class SilentLogger(object):
  def debug(self, msg):
    pass

  def warning(self, msg):
    logger(msg, warnig=True)

  def error(self, msg):
    if 'HTTP Error 403' in str(msg):return
    if 'No such file or directory' in str(msg):return
    logger(msg, error=True)
