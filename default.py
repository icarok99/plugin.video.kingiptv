# -*- coding: utf-8 -*-
import os
import time
from lib.helper import *
import inputstreamhelper
from lib import xtream, tunein, pluto, imdb, api_vod

profile = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.kingiptv')

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
API_CHANNELS = '\x68\x74\x74\x70\x73\x3a\x2f\x2f\x64\x6f\x63\x73\x2e\x67\x6f\x6f\x67\x6c\x65\x2e\x63\x6f\x6d\x2f\x75\x63\x3f\x65\x78\x70\x6f\x72\x74\x3d\x64\x6f\x77\x6e\x6c\x6f\x61\x64\x26\x69\x64\x3d\x31\x31\x45\x4e\x5f\x4a\x59\x48\x4b\x36\x73\x38\x30\x55\x58\x72\x6d\x4d\x48\x47\x76\x47\x50\x79\x66\x75\x63\x32\x54\x37\x63\x39\x6a'
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
    name = param['name']
    description = param['description']
    iconimage = param['iconimage']
    url = param['url']
    plugin = 'plugin://plugin.video.f4mTester/?streamtype=HLSRETRY&name=' + quote_plus(str(name)) + '&iconImage=' + quote_plus(str(iconimage)) + '&thumbnailImage=' + quote_plus(str(iconimage)) + '&description=' + quote_plus(description) + '&url=' + quote_plus(url)
    xbmc.executebuiltin('RunPlugin(%s)' % plugin)

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
            for name, img, page, year, imdb_id in itens:
                addMenuItem({'name': name, 'description': '', 'iconimage': img, 'url': '', 'imdbnumber': imdb_id, 'year': year}, destiny='/play_resolve_movies', folder=False)
            end()
            setview('List')

@route('/find_series')
def find_series():
    search = input_text(heading='Pesquisar')
    if search:
        itens = imdb.IMDBScraper().search_series(search)
        if itens:
            setcontent('tvshows')
            for name, img, page, year, imdb_id in itens:
                addMenuItem({'name': name, 'description': '', 'iconimage': img, 'url': page, 'imdbnumber': imdb_id}, destiny='/open_imdb_seasons')
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
        for name, image, url, description, imdb_id in itens:
            addMenuItem({'name': name, 'description': description, 'iconimage': image, 'url': '', 'imdbnumber': imdb_id}, destiny='/play_resolve_movies', folder=False)
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
        for name, image, url, description, imdb_id in itens:
            addMenuItem({'name': name, 'description': description, 'iconimage': image, 'url': url, 'imdbnumber': imdb_id}, destiny='/open_imdb_seasons')
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
        for name, image, url, description, imdb_id in itens:
            addMenuItem({'name': name, 'description': description, 'iconimage': image, 'url': '', 'imdbnumber': imdb_id}, destiny='/play_resolve_movies', folder=False)
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
        for name, image, url, description, imdb_id in itens:
            addMenuItem({'name': name, 'description': description, 'iconimage': image, 'url': url, 'imdbnumber': imdb_id}, destiny='/open_imdb_seasons')
        if end_ < len(all_items):
            addMenuItem({'name': 'Próxima Página', 'page': page + 1}, destiny='/imdb_series_popular')
        end()
        setview('List')

@route('/open_imdb_seasons')
def open_imdb_seasons(param):
    serie_icon = param.get('iconimage', '')
    serie_name = param.get('name', '')
    url = param.get('url', '')
    imdb_id = param.get('imdbnumber', '')
    itens = imdb.IMDBScraper().imdb_seasons(url)
    if itens:
        setcontent('tvshows')
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
                'episode_title': name,
                'playable': 'true'
            }, destiny='/play_resolve_series', folder=False)
        end()
        setview('List')

@route('/play_resolve_movies')
def play_resolve_movies(param):
    notify('Aguarde')
    name = param.get('name', '')
    iconimage = param.get('iconimage', '')
    imdb_number = param.get('imdbnumber', '')
    description = param.get('description', '')
    year = param.get('year', '')

    result = api_vod.VOD().movie(imdb_number)
    if result and result[0]:
        stream, subtitle_url = result

        url = stream.split('|')[0] if '|' in stream else stream
        headers = stream.split('|', 1)[1] if '|' in stream else ''

        force_as_mp4 = url.lower().endswith(('.mp4', '.str'))

        play_item = xbmcgui.ListItem(path=url)
        play_item.setArt({'thumb': iconimage, 'icon': iconimage, 'fanart': iconimage})
        play_item.setContentLookup(False)

        if subtitle_url:
            play_item.setSubtitles([subtitle_url])

        if force_as_mp4:
            play_item.setProperty('inputstream', 'inputstream.ffmpegdirect')
            play_item.setProperty('inputstream.ffmpegdirect.manifest_type', 'mp4')
            play_item.setMimeType('video/mp4')
        else:
            play_item.setProperty('inputstream', 'inputstream.adaptive')
            play_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
            play_item.setProperty('inputstream.adaptive.original_audio_language', 'pt')

        if headers:
            play_item.setProperty('inputstream.adaptive.stream_headers', headers)
            play_item.setProperty('inputstream.ffmpegdirect.stream_headers', headers)

        info_tag = play_item.getVideoInfoTag()
        info_tag.setTitle(name)
        info_tag.setPlot(description)
        info_tag.setIMDBNumber(imdb_number)
        info_tag.setMediaType('movie')
        if year:
            info_tag.setYear(int(year))

        xbmc.Player().play(item=url, listitem=play_item)
    else:
        notify('Stream Indisponivel')


@route('/play_resolve_series')
def play_resolve_series(param):
    notify('Aguarde')
    serie_name = param.get('serie_name', '')
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

        force_as_mp4 = url.lower().endswith(('.mp4', '.str'))

        display_title = episode_title if episode_title else f'S{season}E{episode.zfill(2)}'

        play_item = xbmcgui.ListItem(path=url)
        play_item.setArt({'thumb': iconimage, 'icon': iconimage, 'fanart': fanart or iconimage})
        play_item.setContentLookup(False)

        if subtitle_url:
            play_item.setSubtitles([subtitle_url])

        if force_as_mp4:
            play_item.setProperty('inputstream', 'inputstream.ffmpegdirect')
            play_item.setProperty('inputstream.ffmpegdirect.manifest_type', 'mp4')
            play_item.setMimeType('video/mp4')
        else:
            play_item.setProperty('inputstream', 'inputstream.adaptive')
            play_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
            play_item.setProperty('inputstream.adaptive.original_audio_language', 'pt')

        if headers:
            play_item.setProperty('inputstream.adaptive.stream_headers', headers)
            play_item.setProperty('inputstream.ffmpegdirect.stream_headers', headers)

        info_tag = play_item.getVideoInfoTag()
        info_tag.setTitle(display_title)
        info_tag.setTvShowTitle(serie_name)
        info_tag.setPlot(description)
        info_tag.setIMDBNumber(imdb_number)
        info_tag.setMediaType('episode')

        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, play_item)
    else:
        notify('Stream Indisponivel')
