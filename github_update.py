# -*- coding: utf-8 -*-
import os
import xbmc
import xbmcgui
import xbmcvfs
import urllib.request
import json

ADDON_ID = 'plugin.video.kingiptv'
ADDON_PATH = xbmcvfs.translatePath(f'special://home/addons/{ADDON_ID}/')

RAW_BASE_URL = 'https://raw.githubusercontent.com/icarok99/plugin.video.kingiptv/main/'
CONTENTS_API_URL = 'https://api.github.com/repos/icarok99/plugin.video.kingiptv/contents/'

def notify(msg):
    xbmcgui.Dialog().notification('KING IPTV - Update', msg, xbmcgui.NOTIFICATION_INFO, 4000)

def make_github_request(url):
    try:
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        notify(f'Erro na requisição: {e}')
        return None

def fetch_all_files(api_url, base_path=""):
    files = []
    items = make_github_request(api_url)
    if not items:
        return files
    for item in items:
        if item['type'] == 'file':
            files.append(base_path + item['name'])
        elif item['type'] == 'dir':
            sub_path = base_path + item['name'] + '/'
            files.extend(fetch_all_files(CONTENTS_API_URL + sub_path, sub_path))
    return files

def download_and_replace_file(path):
    try:
        url = RAW_BASE_URL + path
        dest_path = os.path.join(ADDON_PATH, path)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with urllib.request.urlopen(url) as response:
            content = response.read()
        with open(dest_path, 'wb') as f:
            f.write(content)
        return True
    except Exception as e:
        notify(f'Erro ao atualizar {path}: {e}')
        return False

def update_files():
    files = fetch_all_files(CONTENTS_API_URL)
    if not files:
        notify('Nenhum arquivo encontrado no repositório.')
        return

    updated = False
    for file in files:
        success = download_and_replace_file(file)
        updated = updated or success

    if updated:
        notify('Addon atualizado com sucesso.')
    else:
        notify('Nenhum arquivo foi atualizado.')

if __name__ == '__main__':
    update_files()
