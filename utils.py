from datetime import datetime
import os
import re


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
  print(benedictus.format(name='hotm4rtei', version='Alpha 0.5'))


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


def log_error(message):
  timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
  with open('errosdownload.txt', 'a') as file:
    file.write(f'{timestamp} - {message}\n')


class SilentLogger(object):
  def debug(self, msg):
    pass

  def warning(self, msg):
    log_error(msg)
    pass

  def error(self, msg):
    log_error(msg)
    pass
