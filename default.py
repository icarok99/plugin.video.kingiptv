# -*- coding: utf-8 -*-
import os
import re
import time
import urllib.request
from lib.helper import *
import inputstreamhelper
from lib import xtream, tunein, pluto, imdb, api_vod
from urllib.parse import quote_plus, unquote_plus

# Definindo profile corretamente (caso não venha de helper)
profile = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.kingiptv')

# Atualização automática por data remota
try:
    import github_update
    from datetime import datetime
    import requests

    UPDATE_CHECK_FILE = os.path.join(profile, 'last_checked_date.txt')  # onde gravar a data local
    REMOTE_DATE_URL = 'https://raw.githubusercontent.com/icarok99/plugin.video.kingiptv/main/last_update.txt'

    def get_local_date():
        try:
            with open(UPDATE_CHECK_FILE, 'r') as f:
                return datetime.strptime(f.read().strip(), '%d-%m-%Y')
        except:
            return datetime.strptime('26-07-2025', '%d-%m-%Y')  # data inicial

    def save_local_date(date_str):
        with open(UPDATE_CHECK_FILE, 'w') as f:
            f.write(date_str)

    def is_update_needed_by_date():
        try:
            response = requests.get(REMOTE_DATE_URL, timeout=5)
            if response.status_code == 200:
                remote_date_str = response.text.strip()
                remote_date = datetime.strptime(remote_date_str, '%d-%m-%Y')
                local_date = get_local_date()
                if remote_date > local_date:
                    save_local_date(remote_date_str)
                    return True
        except Exception as e:
            print(f'Erro ao verificar data remota: {e}')
        return False

except Exception as e:
    from xbmcgui import Dialog
    Dialog().notification('Erro na atualização automática', str(e), xbmcgui.NOTIFICATION_ERROR, 5000)

# BASIC CONFIG
TITULO = '::: KING IPTV :::'
API_CHANNELS = '\x68\x74\x74\x70\x73\x3a\x2f\x2f\x6f\x6e\x65\x70\x6c\x61\x79\x68\x64\x2e\x63\x6f\x6d\x2f\x6c\x69\x73\x74\x61\x73\x5f\x6f\x6e\x65\x70\x6c\x61\x79\x2f\x6d\x61\x73\x74\x65\x72\x2e\x74\x78\x74'
API_RADIOS = 'https://gitea.com/joel00/kingaddon/raw/branch/main/radios.json'

if not exists(profile):
    try:
        os.mkdir(profile)
    except:
        pass
IPTV_PROBLEM_LOG = translate(os.path.join(profile, 'iptv_problems_log.txt'))

def get_url(url, headers=None):
    """Faz uma requisição HTTP e retorna o conteúdo."""
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        if headers:
            for key, value in headers.items():
                req.add_header(key, value)
        response = urllib.request.urlopen(req)
        return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        xbmcgui.Dialog().ok("Erro", f"Falha ao conectar: {str(e)}")
        return None

def parse_m3u(m3u_content):
    """Parseia um arquivo M3U e retorna canais organizados por group-title."""
    channels = {}
    lines = m3u_content.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('#EXTM3U'):
            continue
        if line.startswith('#EXTINF'):
            match_name = re.search(r'tvg-name="([^"]+)"', line)
            name = match_name.group(1) if match_name else 'Sem Nome'
            match_logo = re.search(r'tvg-logo="([^"]+)"', line)
            logo = match_logo.group(1) if match_logo else ''
            match_group = re.search(r'group-title="([^"]+)"', line)
            group = match_group.group(1) if match_group else 'Outros'
            url = lines[i + 1].strip() if i + 1 < len(lines) and not lines[i + 1].startswith('#') else ''
            if url:
                if group not in channels:
                    channels[group] = []
                channels[group].append((name, url, logo, ''))
    return channels

@route('/')
def index():
    # === VERIFICAÇÃO DE UPDATE AUTOMÁTICA ===
    try:
        if is_update_needed_by_date():
            from xbmcgui import Dialog
            Dialog().notification('KING IPTV', 'Atualizando...', xbmcgui.NOTIFICATION_INFO, 5000)
            github_update.update_files()
            Dialog().notification('KING IPTV', 'Atualizado com sucesso!', xbmcgui.NOTIFICATION_INFO, 5000)
    except Exception as e:
        from xbmcgui import Dialog
        Dialog().notification('KING IPTV', f'Erro na atualização: {e}', xbmcgui.NOTIFICATION_ERROR, 5000)
    # === FIM DA VERIFICAÇÃO ===

    addMenuItem({'name': TITULO, 'description': ''}, destiny='')
    addMenuItem({'name': 'LISTAS IPTV', 'description': ''}, destiny='/playlistiptv')
    addMenuItem({'name': 'CANAIS PLUTO', 'description': ''}, destiny='/channels_pluto')
    addMenuItem({'name': 'RADIOS', 'description': ''}, destiny='/radios')
    addMenuItem({'name': 'IMDB Filmes', 'description': ''}, destiny='/imdb_movies')
    addMenuItem({'name': 'IMDB Series', 'description': ''}, destiny='/imdb_series')
    end()
    setview('WideList')

@route('/playlistiptv')
def playlistiptv():
    master_content = get_url(API_CHANNELS)
    if master_content:
        lists = [line.strip() for line in master_content.split('\n') if line.strip() and line.startswith('http')]
        for n, url in enumerate(lists, 1):
            addMenuItem({'name': f'LISTA {n}', 'description': '', 'url': url}, destiny='/cat_channels')
        end()
        setview('WideList')
    else:
        notify('Sem lista iptv')

@route('/cat_channels')
def cat_channels(param):
    url_m3u = param['url']
    m3u_content = get_url(url_m3u)
    if m3u_content:
        channels = parse_m3u(m3u_content)
        for group in channels:
            addMenuItem({'name': group, 'description': '', 'url': url_m3u, 'group': group}, destiny='/open_group_channels')
        end()
        setview('WideList')
    else:
        notify(f'Lista {url_m3u} Offline')

@route('/open_group_channels')
def open_group_channels(param):
    url_m3u = param['url']
    group = param['group']
    m3u_content = get_url(url_m3u)
    if m3u_content:
        setcontent('movies')
        channels = parse_m3u(m3u_content)
        for name, link, thumb, desc in channels.get(group, []):
            addMenuItem({'name': name, 'description': desc, 'iconimage': thumb, 'url': link}, destiny='/play_iptv', folder=False)
        end()
        setview('List')
    else:
        notify('Opção indisponível')

@route('/play_iptv')
def play_iptv(param):
    name = param['name']
    description = param['description']
    iconimage = param['iconimage']
    url = param['url']
    plugin = f'plugin://plugin.video.f4mTester/?streamtype=HLSRETRY&name={quote_plus(str(name))}&iconImage={quote_plus(str(iconimage))}&thumbnailImage={quote_plus(str(iconimage))}&description={quote_plus(description)}&url={quote_plus(url)}'
    xbmc.executebuiltin(f'RunPlugin({plugin})')

@route('/channels_pluto')
def channels_pluto(param):
    # o decorator passa params; aceitamos mas não usamos aqui
    channels = pluto.playlist_pluto()
    if channels:
        setcontent('movies')
        for channel_name, desc, thumbnail, stream in channels:
            addMenuItem({'name': channel_name, 'description': desc, 'iconimage': thumbnail, 'url': stream}, destiny='/play_iptv2', folder=False)
        end()
        setview('List')

@route('/play_iptv2')
def play_iptv2(param):
    url = param.get('url', '')
    name = param.get('name', 'Pluto TV')
    description = param.get('description', '')
    iconimage = param.get('iconimage', '')
    
    is_helper = inputstreamhelper.Helper("hls")
    if is_helper.check_inputstream():
        if '|' in url:
            header = unquote_plus(url.split('|')[1])
        play_item = xbmcgui.ListItem(path=url)
        play_item.setContentLookup(False)
        play_item.setArt({"icon": "DefaultVideo.png", "thumb": iconimage})
        play_item.setMimeType("application/vnd.apple.mpegurl")
        play_item.setProperty('inputstream', is_helper.inputstream_addon)
        play_item.setProperty("inputstream.adaptive.manifest_type", "hls")
        if '|' in url:
            play_item.setProperty("inputstream.adaptive.manifest_headers", header)
        play_item.setProperty('inputstream.adaptive.manifest_update_parameter', 'full')
        play_item.setProperty('inputstream.adaptive.is_realtime_stream', 'true')
        
        info = play_item.getVideoInfoTag()
        info.setTitle(name)
        info.setPlot(description)
        info.setMediaType('video')
        
        xbmc.Player().play(item=url, listitem=play_item)

@route('/radios')
def radios():
    tunein.radios_list(API_RADIOS)

@route('/imdb_movies')
def imdb_movies():
    addMenuItem({'name': 'Pesquisar Filmes', 'description': ''}, destiny='/find_movies')
    addMenuItem({'name': 'Filmes - TOP 250', 'description': ''}, destiny='/imdb_movies_250')
    addMenuItem({'name': 'Filmes - Popular', 'description': ''}, destiny='/imdb_movies_popular')
    end()
    setview('WideList')

@route('/imdb_series')
def imdb_series():
    addMenuItem({'name': 'Pesquisar Series', 'description': ''}, destiny='/find_series')
    addMenuItem({'name': 'Series - TOP 250', 'description': ''}, destiny='/imdb_series_250')
    addMenuItem({'name': 'Series - Popular', 'description': ''}, destiny='/imdb_series_popular')
    end()
    setview('WideList')

@route('/find_movies')
def find_movies():
    search = input_text(heading='Pesquisar')
    if search:
        itens = imdb.IMDBScraper().search_movies(search)
        if itens:
            setcontent('movies')
            for name, img, page, year, imdb_id in itens:
                addMenuItem({'name': name, 'description': '', 'iconimage': img, 'url': '', 'imdbnumber': imdb_id, 'year': year}, destiny='/play_resolve_movies', folder=False)
            end()
            setview('Wall')

@route('/find_series')
def find_series():
    search = input_text(heading='Pesquisar')
    if search:
        itens = imdb.IMDBScraper().search_series(search)
        if itens:
            setcontent('tvshows')
            for name, img, page, year, imdb_id in itens:
                addMenuItem({'name': name, 'description': '', 'iconimage': img, 'url': page, 'imdbnumber': imdb_id, 'year': year}, destiny='/open_imdb_seasons')
            end()
            setview('Wall')

@route('/imdb_movies_250')
def movies_250(param=None):
    page = int(param.get('page', 1)) if param else 1
    per_page = 50
    start = (page - 1) * per_page
    end_ = start + per_page

    all_items = imdb.IMDBScraper().movies_250()
    itens = all_items[start:end_]

    if itens:
        setcontent('movies')
        for name, image, url, description, imdb_id in itens:
            addMenuItem({'name': name, 'description': description, 'iconimage': image, 'url': '', 'imdbnumber': imdb_id}, destiny='/play_resolve_movies', folder=False)

        if end_ < len(all_items):
            addMenuItem({'name': 'Próxima Página', 'page': page + 1}, destiny='/imdb_movies_250')

        end()
        setview('Wall')

@route('/imdb_series_250')
def series_250(param=None):
    page = int(param.get('page', 1)) if param else 1
    per_page = 50
    start = (page - 1) * per_page
    end_ = start + per_page

    all_items = imdb.IMDBScraper().series_250()
    itens = all_items[start:end_]

    if itens:
        setcontent('tvshows')
        for name, image, url, description, imdb_id in itens:
            addMenuItem({'name': name, 'description': description, 'iconimage': image, 'url': url, 'imdbnumber': imdb_id}, destiny='/open_imdb_seasons')

        if end_ < len(all_items):
            addMenuItem({'name': 'Próxima Página', 'page': page + 1}, destiny='/imdb_series_250')

        end()
        setview('Wall')

@route('/imdb_movies_popular')
def movies_popular(param=None):
    page = int(param.get('page', 1)) if param else 1
    per_page = 50
    start = (page - 1) * per_page
    end_ = start + per_page

    all_items = imdb.IMDBScraper().movies_popular()
    itens = all_items[start:end_]

    if itens:
        setcontent('movies')
        for name, image, url, description, imdb_id in itens:
            addMenuItem({'name': name, 'description': description, 'iconimage': image, 'url': '', 'imdbnumber': imdb_id}, destiny='/play_resolve_movies', folder=False)

        if end_ < len(all_items):
            addMenuItem({'name': 'Próxima Página', 'page': page + 1}, destiny='/imdb_movies_popular')

        end()
        setview('Wall')

@route('/imdb_series_popular')
def series_popular(param=None):
    page = int(param.get('page', 1)) if param else 1
    per_page = 50
    start = (page - 1) * per_page
    end_ = start + per_page

    all_items = imdb.IMDBScraper().series_popular()
    itens = all_items[start:end_]

    if itens:
        setcontent('tvshows')
        for name, image, url, description, imdb_id in itens:
            addMenuItem({'name': name, 'description': description, 'iconimage': image, 'url': url, 'imdbnumber': imdb_id}, destiny='/open_imdb_seasons')

        if end_ < len(all_items):
            addMenuItem({'name': 'Próxima Página', 'page': page + 1}, destiny='/imdb_series_popular')

        end()
        setview('Wall')

@route('/open_imdb_seasons')
def open_imdb_seasons(param):
    serie_icon = param.get('iconimage', '')
    serie_name = param.get('name', '')
    url = param.get('url', '')
    imdb_id = param.get('imdbnumber', '')
    itens = imdb.IMDBScraper().imdb_seasons(url)
    if itens:
        setcontent('tvshows')
        try:
            addMenuItem({'name': f'::: {serie_name}:::', 'description': '', 'iconimage': serie_icon}, destiny='')
        except:
            pass
        for season_number, name, url_season in itens:
            addMenuItem({'name': name, 'description': '', 'iconimage': serie_icon, 'url': url_season, 'imdbnumber': imdb_id, 'season': season_number, 'serie_name': serie_name}, destiny='/open_imdb_episodes')
        end()
        setview('List')

@route('/open_imdb_episodes')
def open_imdb_episodes(param):
    serie_icon = param.get('iconimage', '')
    serie_name = param.get('serie_name', '')
    url = param.get('url', '')
    imdb_id = param.get('imdbnumber', '')
    season = param.get('season', '')
    itens = imdb.IMDBScraper().imdb_episodes(url)
    if itens:
        setcontent('tvshows')
        try:
            addMenuItem({'name': f'::: {serie_name} - S{season}:::', 'description': '', 'iconimage': serie_icon}, destiny='')
        except:
            pass 
        for episode_number, name, img, fanart, description in itens:
            name_full = f'{episode_number} - {name}'  # Ex.: "1 - A Whole New Whirled"
            addMenuItem({
                'name': name_full,  # Usado no menu
                'description': description,
                'iconimage': img,
                'fanart': fanart,
                'imdbnumber': imdb_id,
                'season': season,
                'episode': str(episode_number),
                'serie_name': serie_name,
                'episode_title': name,  # Passa o título do episódio
                'playable': 'true'
            }, destiny='/play_resolve_series', folder=False)
        end()
        setview('List')

@route('/play_resolve_movies')
def play_resolve_movies(param):
    notify('Aguarde')
    name = param.get('name', '')
    iconimage = param.get('iconimage', '')
    imdb = param.get('imdbnumber', '')
    description = param.get('description', '')
    year = param.get('year', '')
    
    url = api_vod.VOD().movie(imdb)
    if url:
        notify('Escolha o audio portugues nos ajustes')
        is_helper = inputstreamhelper.Helper("hls")
        if is_helper.check_inputstream():
            if '|' in url:
                header = unquote_plus(url.split('|')[1])
            play_item = xbmcgui.ListItem(path=url)
            play_item.setContentLookup(False)
            play_item.setArt({"icon": "DefaultVideo.png", "thumb": iconimage})
            play_item.setMimeType("application/vnd.apple.mpegurl")
            play_item.setProperty('inputstream', is_helper.inputstream_addon)
            play_item.setProperty("inputstream.adaptive.manifest_type", "hls")
            if '|' in url:
                play_item.setProperty("inputstream.adaptive.manifest_headers", header)
            play_item.setProperty('inputstream.adaptive.manifest_update_parameter', 'full')
            play_item.setProperty('inputstream.adaptive.is_realtime_stream', 'true')
            play_item.setProperty('inputstream.adaptive.original_audio_language', 'pt')
            
            info = play_item.getVideoInfoTag()
            info.setTitle(name)
            info.setPlot(description)
            info.setIMDBNumber(str(imdb))
            info.setMediaType('movie')
            if year:
                info.setYear(int(year))
            
            xbmc.Player().play(item=url, listitem=play_item)
    else:
        notify('Stream Indisponivel')

@route('/play_resolve_series')
def play_resolve_series(param):
    notify('Aguarde')
    serie_name = param.get('serie_name', '')
    season = param.get('season', '')
    episode = param.get('episode', '')
    iconimage = param.get('iconimage', '')
    imdb = param.get('imdbnumber', '')
    description = param.get('description', '')
    fanart = param.get('fanart', '')
    episode_title = param.get('episode_title', '')  # Recupera o título do episódio
    
    # Formata o título do episódio, com fallback caso episode_title esteja vazio
    display_title = episode_title if episode_title else f'Episode {episode}'
    
    url = api_vod.VOD().tvshows(imdb, season, episode)
    if url:
        notify('Escolha o audio portugues nos ajustes')
        is_helper = inputstreamhelper.Helper("hls")
        if is_helper.check_inputstream():
            if '|' in url:
                header = unquote_plus(url.split('|')[1])
            play_item = xbmcgui.ListItem(path=url)
            play_item.setContentLookup(False)
            play_item.setArt({"icon": "DefaultVideo.png", "thumb": iconimage, "fanart": fanart})
            play_item.setMimeType("application/vnd.apple.mpegurl")
            play_item.setProperty('inputstream', is_helper.inputstream_addon)
            play_item.setProperty("inputstream.adaptive.manifest_type", "hls")
            if '|' in url:
                play_item.setProperty("inputstream.adaptive.manifest_headers", header)
            play_item.setProperty('inputstream.adaptive.manifest_update_parameter', 'full')
            play_item.setProperty('inputstream.adaptive.is_realtime_stream', 'true')
            play_item.setProperty('inputstream.adaptive.original_audio_language', 'pt')
            
            info = play_item.getVideoInfoTag()
            info.setTitle(display_title)  # Define o título do episódio (ex.: "A Whole New Whirled")
            info.setTvShowTitle(serie_name)  # Define o título da série (ex.: "Pacificador")
            info.setPlot(description)
            info.setIMDBNumber(str(imdb))
            info.setSeason(int(season))
            info.setEpisode(int(episode))
            info.setMediaType('episode')
            
            xbmcplugin.setResolvedUrl(handle, True, play_item)
    else:
        notify('Stream Indisponivel')
