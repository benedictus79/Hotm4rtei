import os
import re
import random
from datetime import datetime
from time import sleep


def benedictus_ascii_art():
  benedictus = """
     _  _  ___ _____ __  __ _ _  ___ _____ ___ ___ 
    | || |/ _ \_   _|  \/  | | || _ \_   _| __|_ _|
    | __ | (_) || | | |\/| |_  _|   / | | | _| | | 
    |_||_|\___/ |_| |_|  |_| |_||_|_\ |_| |___|___|
    
  Author: Benedictus ©
  Community: https://t.me/alex4ndriagroup
  Script: {name}
  Version: {version}
  """
  print(benedictus.format(name='hotm4rtei', version='Legend 1.2'))


def clear_screen():
  os.system('cls || clear')


def create_folder(folder_name):
  path = os.path.join(os.getcwd(), folder_name)

  if not os.path.exists(path):
    os.mkdir(path)

  return path


def clear_folder_name(name, is_file=None, ext=''):
  if is_file:
    name, ext = os.path.splitext(name)
  sanitized_base = re.sub(r'[<>:."/\\|?*]|\s+|\.$', ' ', name).strip()
  return sanitized_base + ext if ext else sanitized_base


def shorten_folder_name(full_path, max_length=245):
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
  sleep(random.randint(3, 7))


def remove_file(file_path):
  try:
    os.remove(file_path)
  except OSError as e:
    msg = f"Erro ao remover o arquivo '{file_path}': {e.strerror}"
    logger(msg, error=True)


class SilentLogger(object):
  def debug(self, msg):
    pass

  def warning(self, msg):
    logger(msg, warning=True)

  def error(self, msg):
    if 'HTTP Error 403' in str(msg):return
    if 'No such file or directory' in str(msg):return
    logger(msg, error=True)

