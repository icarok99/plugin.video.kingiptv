# -*- coding: utf-8 -*-
import os
import time
from lib.helper import *
import inputstreamhelper
from lib import xtream, tunein, pluto, imdb, api_vod, hlsretry

profile = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.kingiptv')

def stop_player():
    try:
        player = xbmc.Player()
        if player.isPlaying():
            player.stop()
            xbmc.sleep(300)
    except:
        pass

try:
    import github_update
    from datetime import datetime
    import requests

    UPDATE_CHECK_FILE = os.path.join(profile, 'last_checked_date.txt')
    REMOTE_DATE_URL = 'https://raw.githubusercontent.com/icarok99/plugin.video.kingiptv/main/last_update.txt'

    def get_local_date():
        try:
            with open(UPDATE_CHECK_FILE, 'r') as f:
                return datetime.strptime(f.read().strip(), '%d-%m-%Y')
        except:
            return datetime.strptime('19-12-2025', '%d-%m-%Y')

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

TITULO = '::: KING IPTV :::'
API_CHANNELS = '\x68\x74\x74\x70\x73\x3a\x2f\x2f\x64\x6f\x63\x73\x2e\x67\x6f\x6f\x67\x6c\x65\x2e\x63\x6f\x6d\x2f\x75\x63\x3f\x65\x78\x70\x6f\x72\x74\x3d\x64\x6f\x77\x6e\x6c\x6f\x61\x64\x26\x69\x64\x3d\x31\x67\x52\x53\x61\x72\x30\x49\x79\x32\x6f\x47\x65\x70\x4c\x33\x4c\x6b\x4d\x74\x43\x62\x77\x54\x7a\x67\x53\x67\x68\x41\x73\x77\x36'
API_RADIOS = '\x68\x74\x74\x70\x73\x3a\x2f\x2f\x64\x6f\x63\x73\x2e\x67\x6f\x6f\x67\x6c\x65\x2e\x63\x6f\x6d\x2f\x75\x63\x3f\x65\x78\x70\x6f\x72\x74\x3d\x64\x6f\x77\x6e\x6c\x6f\x61\x64\x26\x69\x64\x3d\x31\x31\x46\x34\x63\x48\x4a\x49\x47\x6c\x6d\x52\x70\x42\x56\x6a\x79\x4c\x5f\x34\x42\x56\x30\x6e\x6f\x7a\x4d\x4d\x53\x4e\x54\x6f\x62'

if not exists(profile):
    try:
        os.mkdir(profile)
    except:
        pass
IPTV_PROBLEM_LOG = translate(os.path.join(profile, 'iptv_problems_log.txt'))

@route('/')
def index():
    try:
        if is_update_needed_by_date():
            from xbmcgui import Dialog
            Dialog().notification('KING IPTV', 'Atualizando...', xbmcgui.NOTIFICATION_INFO, 5000)
            github_update.update_files()
            Dialog().notification('KING IPTV', 'Atualizado com sucesso!', xbmcgui.NOTIFICATION_INFO, 5000)
    except Exception as e:
        from xbmcgui import Dialog
        Dialog().notification('KING IPTV', f'Erro na atualização: {e}', xbmcgui.NOTIFICATION_ERROR, 5000)

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
    iptv = xtream.parselist(API_CHANNELS)
    if iptv:
        for n, (dns, username, password) in enumerate(iptv):
            n = n + 1
            addMenuItem({'name': 'LISTA {0}'.format(str(n)), 'description': '', 'dns': dns, 'username': str(username), 'password': str(password)}, destiny='/cat_channels')
        end()
        setview('WideList') 
    else:
        notify('Sem lista iptv') 

@route('/cat_channels')
def cat_channels(param):
    dns = param['dns']
    username = param['username']
    password = param['password']
    cat = xtream.API(dns,username,password).channels_category()
    if cat:
        for i in cat:
            name, url = i
            addMenuItem({'name': name, 'description': '', 'dns': dns, 'username': str(username), 'password': str(password), 'url': url}, destiny='/open_channels')
        end()
        setview('WideList')
    else:
        url_problem = '{0}/get.php?username={1}&password={2}\n'.format(dns,username,password)
        if six.PY2:
            import io
            open_file = lambda filename, mode: io.open(filename, mode, encoding='utf-8')
        else:
            open_file = lambda filename, mode: open(filename, mode, encoding='utf-8')
        if exists(IPTV_PROBLEM_LOG):
            check = False
            with open(IPTV_PROBLEM_LOG, "r") as arquivo:
                if url_problem in arquivo.read():
                    check = True
        else:
            check = False
        with open_file(IPTV_PROBLEM_LOG, "a") as arquivo:
            if not check:
                arquivo.write(url_problem)
        notify('Lista Offline')

@route('/open_channels')
def open_channels(param):
    dns = param['dns']
    username = param['username']
    password = param['password']
    url = param['url'] 
    open_ = xtream.API(dns,username,password).channels_open(url)
    if open_:
        setcontent('movies')
        for i in open_:
            name,link,thumb,desc = i
            addMenuItem({'name': name, 'description': desc, 'iconimage': thumb, 'url': link}, destiny='/play_iptv', folder=False)
        end()
        setview('List')
    else:
        notify('Opção indisponivel')

@route('/play_iptv')
def play_iptv(param):
    name = param.get('name', 'Canal IPTV')
    description = param.get('description', '')
    iconimage = param.get('iconimage', '')
    url = param.get('url', '')
    if '|' in url: url = url.split('|')[0]
    try: hlsretry.XtreamProxy().start()
    except: pass
    proxy_url = f'http://127.0.0.1:{hlsretry.PORT_NUMBER}/?url={quote_plus(url)}'
    play_item = xbmcgui.ListItem(path=proxy_url)
    play_item.setContentLookup(False)
    play_item.setArt({"icon": iconimage or "DefaultVideo.png", "thumb": iconimage or "DefaultVideo.png"})
    play_item.setMimeType("application/vnd.apple.mpegurl")
    info_tag = play_item.getVideoInfoTag() if hasattr(play_item, 'getVideoInfoTag') else None
    if info_tag:
        info_tag.setTitle(name)
        info_tag.setPlot(description)
        info_tag.setMediaType('video')
    else:
        play_item.setInfo('video', {'title': name, 'plot': description, 'mediatype': 'video'})
    xbmc.Player().play(proxy_url, play_item)

@route('/channels_pluto')
def channels_pluto(param=None):
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

        play_item = xbmcgui.ListItem(path=url)
        play_item.setContentLookup(False)
        play_item.setArt({"icon": "DefaultVideo.png", "thumb": iconimage})
        play_item.setMimeType("application/vnd.apple.mpegurl")

        play_item.setProperty('inputstreamaddon', is_helper.inputstream_addon)
        play_item.setProperty("inputstream.adaptive.manifest_type", "hls")

        if '|' in url:
            header = unquote_plus(url.split('|')[1])
            play_item.setProperty("inputstream.adaptive.stream_headers", header)

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
            for movie_name, img, page, year, imdb_id, original_name in itens:
                addMenuItem({
                    'name': movie_name,
                    'description': '',
                    'iconimage': img,
                    'url': '',
                    'imdbnumber': imdb_id,
                    'year': year,
                    'movie_name': movie_name,
                    'original_name': original_name
                }, destiny='/play_resolve_movies', folder=False)
            end()
            setview('List')

@route('/find_series')
def find_series():
    search = input_text(heading='Pesquisar')
    if search:
        itens = imdb.IMDBScraper().search_series(search)
        if itens:
            setcontent('tvshows')
            for serie_name, img, page, year, imdb_id, original_name in itens:
                addMenuItem({
                    'name': serie_name,
                    'description': '',
                    'iconimage': img,
                    'url': page,
                    'imdbnumber': imdb_id,
                    'serie_name': serie_name,
                    'original_name': original_name
                }, destiny='/open_imdb_seasons')
            end()
            setview('List')

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
        for movie_name, image, url, description, imdb_id, original_name in itens:
            addMenuItem({
                'name': movie_name,
                'description': description,
                'iconimage': image,
                'url': '',
                'imdbnumber': imdb_id,
                'movie_name': movie_name,
                'original_name': original_name
            }, destiny='/play_resolve_movies', folder=False)
        if end_ < len(all_items):
            addMenuItem({'name': 'Próxima Página', 'page': page + 1}, destiny='/imdb_movies_250')
        end()
        setview('List')

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
        for serie_name, image, url, description, imdb_id, original_name in itens:
            addMenuItem({
                'name': serie_name,
                'description': description,
                'iconimage': image,
                'url': url,
                'imdbnumber': imdb_id,
                'serie_name': serie_name,
                'original_name': original_name
            }, destiny='/open_imdb_seasons')
        if end_ < len(all_items):
            addMenuItem({'name': 'Próxima Página', 'page': page + 1}, destiny='/imdb_series_250')
        end()
        setview('List')

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
        for movie_name, image, url, description, imdb_id, original_name in itens:
            addMenuItem({
                'name': movie_name,
                'description': description,
                'iconimage': image,
                'url': '',
                'imdbnumber': imdb_id,
                'movie_name': movie_name,
                'original_name': original_name
            }, destiny='/play_resolve_movies', folder=False)
        if end_ < len(all_items):
            addMenuItem({'name': 'Próxima Página', 'page': page + 1}, destiny='/imdb_movies_popular')
        end()
        setview('List')

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
        for serie_name, image, url, description, imdb_id, original_name in itens:
            addMenuItem({
                'name': serie_name,
                'description': description,
                'iconimage': image,
                'url': url,
                'imdbnumber': imdb_id,
                'serie_name': serie_name,
                'original_name': original_name
            }, destiny='/open_imdb_seasons')
        if end_ < len(all_items):
            addMenuItem({'name': 'Próxima Página', 'page': page + 1}, destiny='/imdb_series_popular')
        end()
        setview('List')

@route('/open_imdb_seasons')
def open_imdb_seasons(param):
    serie_icon = param.get('iconimage', '')
    serie_name = param.get('serie_name', param.get('name', ''))
    original_name = param.get('original_name', '')
    url = param.get('url', '')
    imdb_id = param.get('imdbnumber', '')
    itens = imdb.IMDBScraper().imdb_seasons(url)
    if itens:
        setcontent('tvshows')
        for season_number, name, url_season in itens:
            addMenuItem({
                'name': name,
                'description': '',
                'iconimage': serie_icon,
                'url': url_season,
                'imdbnumber': imdb_id,
                'season': season_number,
                'serie_name': serie_name,
                'original_name': original_name
            }, destiny='/open_imdb_episodes')
        end()
        setview('List')

@route('/open_imdb_episodes')
def open_imdb_episodes(param):
    serie_icon = param.get('iconimage', '')
    serie_name = param.get('serie_name', '')
    original_name = param.get('original_name', '')
    url = param.get('url', '')
    imdb_id = param.get('imdbnumber', '')
    season = param.get('season', '')
    itens = imdb.IMDBScraper().imdb_episodes(url)
    if itens:
        setcontent('tvshows')
        for episode_number, name, img, fanart, description in itens:
            name_full = f'{episode_number} - {name}'
            addMenuItem({
                'name': name_full,
                'description': description,
                'iconimage': img,
                'fanart': fanart,
                'imdbnumber': imdb_id,
                'season_num': season,
                'episode_num': str(episode_number),
                'serie_name': serie_name,
                'original_name': original_name,
                'episode_title': name,
                'playable': 'true'
            }, destiny='/play_resolve_series', folder=False)
        end()
        setview('List')

@route('/play_resolve_movies')
def play_resolve_movies(param):
    notify('Aguarde')
    stop_player()
    movie_name = param.get('movie_name', param.get('name', ''))
    iconimage = param.get('iconimage', '')
    imdb_number = param.get('imdbnumber', '')
    description = param.get('description', '')
    year = param.get('year', '')
    original_name = param.get('original_name', '')

    result = api_vod.VOD().movie(imdb_number)
    if result and result[0]:
        stream, subtitle_url = result

        url = stream.split('|')[0] if '|' in stream else stream
        headers = stream.split('|', 1)[1] if '|' in stream else ''

        is_direct_file = url.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm', '.ts'))

        play_item = xbmcgui.ListItem(path=url)
        play_item.setArt({'thumb': iconimage, 'icon': iconimage, 'fanart': iconimage})
        play_item.setContentLookup(False)

        if subtitle_url:
            play_item.setSubtitles([subtitle_url])

        if is_direct_file:
            play_item.setMimeType('video/mp4')
            if headers:
                url_with_headers = f"{url}|{headers}&User-Agent=Mozilla/5.0&Referer=https://google.com"
                play_item = xbmcgui.ListItem(path=url_with_headers)
        else:
            play_item.setProperty('inputstream', 'inputstream.adaptive')
            play_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
            play_item.setProperty('inputstream.adaptive.original_audio_language', 'pt')
            if headers:
                play_item.setProperty('inputstream.adaptive.stream_headers', headers)

        kodi_version = int(xbmc.getInfoLabel('System.BuildVersion').split('.')[0])
        if kodi_version >= 20:
            info_tag = play_item.getVideoInfoTag()
            info_tag.setTitle(movie_name)
            info_tag.setPlot(description)
            info_tag.setIMDBNumber(imdb_number)
            info_tag.setMediaType('movie')
            info_tag.setOriginalTitle(original_name)
            if year:
                info_tag.setYear(int(year))
        else:
            info_dict = {
                'title': movie_name,
                'plot': description,
                'imdbnumber': imdb_number,
                'mediatype': 'movie',
                'originaltitle': original_name
            }
            if year:
                info_dict['year'] = int(year)
            play_item.setInfo('video', info_dict)

        notify('Escolha o audio portugues nos ajustes')
        xbmc.Player().play(item=url, listitem=play_item)
    else:
        notify('Stream Indisponivel')

@route('/play_resolve_series')
def play_resolve_series(param):
    notify('Aguarde')
    stop_player()
    serie_name = param.get('serie_name', '')
    original_name = param.get('original_name', '')
    season = param.get('season_num', '')
    episode = param.get('episode_num', '')
    episode_title = param.get('episode_title', '')
    iconimage = param.get('iconimage', '')
    fanart = param.get('fanart', '')
    imdb_number = param.get('imdbnumber', '')
    description = param.get('description', '')

    result = api_vod.VOD().tvshows(imdb_number, season, episode)
    if result and result[0]:
        stream, subtitle_url = result

        url = stream.split('|')[0] if '|' in stream else stream
        headers = stream.split('|', 1)[1] if '|' in stream else ''

        is_direct_file = url.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm', '.ts'))

        display_title = episode_title if episode_title else f'S{season}E{episode.zfill(2)}'

        play_item = xbmcgui.ListItem(path=url)
        play_item.setArt({'thumb': iconimage, 'icon': iconimage, 'fanart': fanart or iconimage})
        play_item.setContentLookup(False)

        if subtitle_url:
            play_item.setSubtitles([subtitle_url])

        if is_direct_file:
            play_item.setMimeType('video/mp4')
            if headers:
                url_with_headers = f"{url}|{headers}&User-Agent=Mozilla/5.0&Referer=https://google.com"
                play_item = xbmcgui.ListItem(path=url_with_headers)
        else:
            play_item.setProperty('inputstream', 'inputstream.adaptive')
            play_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
            play_item.setProperty('inputstream.adaptive.original_audio_language', 'pt')
            if headers:
                play_item.setProperty('inputstream.adaptive.stream_headers', headers)

        kodi_version = int(xbmc.getInfoLabel('System.BuildVersion').split('.')[0])
        if kodi_version >= 20:
            info_tag = play_item.getVideoInfoTag()
            info_tag.setTitle(display_title)
            info_tag.setTvShowTitle(serie_name)
            info_tag.setOriginalTitle(original_name)
            info_tag.setPlot(description)
            info_tag.setIMDBNumber(imdb_number)
            info_tag.setMediaType('episode')
        else:
            info_dict = {
                'title': display_title,
                'tvshowtitle': serie_name,
                'originaltitle': original_name,
                'plot': description,
                'imdbnumber': imdb_number,
                'mediatype': 'episode'
            }
            play_item.setInfo('video', info_dict)

        notify('Escolha o audio portugues nos ajustes')
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, play_item)
    else:
        notify('Stream Indisponivel')
