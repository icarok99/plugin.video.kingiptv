# -*- coding: utf-8 -*-

import os
import time
import json
import threading
from lib.helper import *
import inputstreamhelper
from lib import xtream, tunein, pluto, imdb, api_vod, hlsretry

try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode

from lib.player import get_player
from lib.database import KingDatabase
from lib.loading_window import loading_manager

db = KingDatabase()

_addon = xbmcaddon.Addon()

def getString(string_id):
    return _addon.getLocalizedString(string_id)

profile = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.kingiptv')

try:
    import github_update
    from datetime import datetime
    import requests

    UPDATE_CHECK_FILE = os.path.join(profile, 'last_checked_date.txt')
    REMOTE_DATE_URL = 'https://raw.githubusercontent.com/icarok99/plugin.video.kingiptv/main/last_update.txt'

    def get_local_date():
        if os.path.exists(UPDATE_CHECK_FILE):
            with open(UPDATE_CHECK_FILE, 'r') as f:
                content = f.read().strip()
                if content:
                    try:
                        return datetime.strptime(content, '%d-%m-%Y')
                    except ValueError:
                        pass
        return datetime.strptime('15-02-2026', '%d-%m-%Y')

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
    Dialog().notification(getString(32026), str(e), xbmcgui.NOTIFICATION_ERROR, 5000)

TITULO = '::: KING IPTV :::'
API_CHANNELS = '\x68\x74\x74\x70\x73\x3a\x2f\x2f\x64\x6f\x63\x73\x2e\x67\x6f\x6f\x67\x6c\x65\x2e\x63\x6f\x6d\x2f\x75\x63\x3f\x65\x78\x70\x6f\x72\x74\x3d\x64\x6f\x77\x6e\x6c\x6f\x61\x64\x26\x69\x64\x3d\x31\x67\x52\x53\x61\x72\x30\x49\x79\x32\x6f\x47\x65\x70\x4c\x33\x4c\x6b\x4d\x74\x43\x62\x77\x54\x7a\x67\x53\x67\x68\x41\x73\x77\x36'
API_RADIOS = '\x68\x74\x74\x70\x73\x3a\x2f\x2f\x64\x6f\x63\x73\x2e\x67\x6f\x6f\x67\x6c\x65\x2e\x63\x6f\x6d\x2f\x75\x63\x3f\x65\x78\x70\x6f\x72\x74\x3d\x64\x6f\x77\x6e\x6c\x6f\x61\x64\x26\x69\x64\x3d\x31\x31\x46\x34\x63\x48\x4a\x49\x47\x6c\x6d\x52\x70\x42\x56\x6a\x79\x4c\x5f\x34\x42\x56\x30\x6e\x6f\x7a\x4d\x4d\x53\x4e\x54\x6f\x62'

if not exists(profile):
    try:
        os.makedirs(profile)
    except OSError as e:
        if e.errno != 17:
            pass
IPTV_PROBLEM_LOG = translate(os.path.join(profile, 'iptv_problems_log.txt'))

def build_series_playlist(imdb_number, season_num, current_episode_num, serie_name, original_name, all_episodes):
    if not all_episodes or not isinstance(all_episodes, list):
        return
    
    if not isinstance(season_num, int) or not isinstance(current_episode_num, int):
        return
    
    playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    
    for episode_data in all_episodes:
        if not isinstance(episode_data, dict):
            continue
            
        ep_num = episode_data.get('episode')
        if not ep_num or not isinstance(ep_num, int):
            continue
            
        name = episode_data.get('episode_title', '')
        img = episode_data.get('thumbnail', '')
        fanart = episode_data.get('fanart', '')
        description = episode_data.get('description', '')
        
        if ep_num > current_episode_num:
            params = {
                'serie_name': serie_name,
                'original_name': original_name,
                'season_num': str(season_num),
                'episode_num': str(ep_num),
                'episode_title': name,
                'iconimage': img,
                'fanart': fanart,
                'imdbnumber': imdb_number,
                'description': description
            }
            
            plugin_url = 'plugin://plugin.video.kingiptv/play_resolve_series/{}'.format(urlencode(params))
            
            list_item = xbmcgui.ListItem('{}x{} {}'.format(season_num, str(ep_num).zfill(2), name) if name else '{}x{}'.format(season_num, str(ep_num).zfill(2)))
            list_item.setArt({'thumb': img, 'icon': img, 'fanart': fanart or img})
            
            kodi_version = int(xbmc.getInfoLabel('System.BuildVersion').split('.')[0])
            if kodi_version >= 20:
                info_tag = list_item.getVideoInfoTag()
                info_tag.setTitle('{}x{} {}'.format(season_num, str(ep_num).zfill(2), name) if name else '{}x{}'.format(season_num, str(ep_num).zfill(2)))
                info_tag.setTvShowTitle(serie_name)
                info_tag.setPlot(description)
                info_tag.setMediaType('episode')
                info_tag.setSeason(season_num)
                info_tag.setEpisode(ep_num)
            else:
                list_item.setInfo('video', {
                    'title': '{}x{} {}'.format(season_num, str(ep_num).zfill(2), name) if name else '{}x{}'.format(season_num, str(ep_num).zfill(2)),
                    'tvshowtitle': serie_name,
                    'plot': description,
                    'mediatype': 'episode',
                    'season': season_num,
                    'episode': ep_num,
                })
            
            playlist.add(url=plugin_url, listitem=list_item)

@route('/')
def index():
    try:
        if is_update_needed_by_date():
            from xbmcgui import Dialog
            Dialog().notification('KING IPTV', getString(32023), xbmcgui.NOTIFICATION_INFO, 5000)
            github_update.update_files()
            Dialog().notification('KING IPTV', getString(32024), xbmcgui.NOTIFICATION_INFO, 5000)
    except Exception as e:
        from xbmcgui import Dialog
        Dialog().notification('KING IPTV', '{}: {}'.format(getString(32026), e), xbmcgui.NOTIFICATION_ERROR, 5000)

    addMenuItem({'name': TITULO, 'description': ''}, destiny='')
    addMenuItem({'name': getString(32000), 'description': ''}, destiny='/playlistiptv')
    addMenuItem({'name': getString(32001), 'description': ''}, destiny='/channels_pluto')
    addMenuItem({'name': getString(32002), 'description': ''}, destiny='/radios')
    addMenuItem({'name': getString(32003), 'description': ''}, destiny='/imdb_movies')
    addMenuItem({'name': getString(32004), 'description': ''}, destiny='/imdb_series')
    addMenuItem({'name': getString(32005)}, destiny='/settings')
    end()
    setview('WideList')

@route('/settings')
def settings():
    addon = xbmcaddon.Addon()
    addon.openSettings()

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
        notify(getString(32013))

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
        notify(getString(32014))

@route('/open_channels')
def open_channels(param):
    dns = param['dns']
    username = param['username']
    password = param['password']
    url = param['url'] 
    open_ = xtream.API(dns,username,password).channels_open(url)
    if open_:
        setcontent('videos')
        for i in open_:
            name,link,thumb,desc = i
            addMenuItem({'name': name, 'description': desc, 'iconimage': thumb, 'url': link}, destiny='/play_iptv', folder=False)
        end()
        setview('WideList')
    else:
        notify(getString(32015))

@route('/play_iptv')
def play_iptv(param):
    name = param.get('name', getString(32029))
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
        play_item.setInfo('video', {'title': name, 'plot': description})
    xbmc.Player().play(proxy_url, play_item)

@route('/channels_pluto')
def channels_pluto():
    channels = pluto.GET_CHANNELS()
    if channels:
        setcontent('videos')
        for i in channels:
            name, slug, thumb, desc = i
            addMenuItem({'name': name, 'description': desc, 'iconimage': thumb, 'slug': slug}, destiny='/play_pluto')
        end()
        setview('List')
    else:
        notify(getString(32018))

@route('/play_pluto')
def play_pluto(param):
    slug = param.get('slug', '')
    name = param.get('name', '')
    iconimage = param.get('iconimage', '')
    description = param.get('description', '')
    url = pluto.URL_PLAY(slug)
    if url:
        play_item = xbmcgui.ListItem(path=url)
        play_item.setContentLookup(False)
        play_item.setMimeType("application/vnd.apple.mpegurl")
        play_item.setArt({"icon": iconimage or "DefaultVideo.png", "thumb": iconimage or "DefaultVideo.png"})
        info_tag = play_item.getVideoInfoTag() if hasattr(play_item, 'getVideoInfoTag') else None
        if info_tag:
            info_tag.setTitle(name)
            info_tag.setPlot(description)
            info_tag.setMediaType('video')
        else:
            play_item.setInfo('video', {'title': name, 'plot': description})
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, play_item)
    else:
        notify(getString(32016))

@route('/radios')
def radios():
    radios_ = tunein.parselist(API_RADIOS)
    if radios_:
        for i in radios_:
            name, url = i
            addMenuItem({'name': name, 'description': '', 'url': url}, destiny='/play_radio')
        end()
        setview('List')
    else:
        notify(getString(32017))

@route('/play_radio')
def play_radio(param):
    name = param.get('name', '')
    url = param.get('url', '')
    if url:
        play_item = xbmcgui.ListItem(path=url)
        play_item.setContentLookup(False)
        play_item.setArt({"icon": "DefaultAudio.png", "thumb": "DefaultAudio.png"})
        info_tag = play_item.getVideoInfoTag() if hasattr(play_item, 'getVideoInfoTag') else None
        if info_tag:
            info_tag.setTitle(name)
            info_tag.setMediaType('song')
        else:
            play_item.setInfo('music', {'title': name})
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, play_item)

@route('/imdb_movies')
def imdb_movies():
    addMenuItem({'name': getString(32006), 'description': ''}, destiny='/find_movies')
    addMenuItem({'name': getString(32007), 'description': ''}, destiny='/imdb_movies_250')
    addMenuItem({'name': getString(32008), 'description': ''}, destiny='/imdb_movies_popular')
    end()
    setview('List')

@route('/imdb_series')
def imdb_series():
    addMenuItem({'name': getString(32009), 'description': ''}, destiny='/find_series')
    addMenuItem({'name': getString(32010), 'description': ''}, destiny='/imdb_series_250')
    addMenuItem({'name': getString(32011), 'description': ''}, destiny='/imdb_series_popular')
    end()
    setview('List')

@route('/find_movies')
def find_movies():
    keyboard = xbmc.Keyboard('', getString(32027))
    keyboard.doModal()
    if keyboard.isConfirmed():
        query = keyboard.getText()
        if query:
            results = imdb.IMDBScraper().search_movies(query)
            if results:
                setcontent('movies')
                for movie_name, image, url, description, imdb_id, original_name, year in results:
                    addMenuItem({
                        'name': movie_name,
                        'description': description,
                        'iconimage': image,
                        'fanart': image,
                        'url': '',
                        'imdbnumber': imdb_id,
                        'movie_name': movie_name,
                        'original_name': original_name,
                        'year': year,
                        'playable': True
                    }, destiny='/play_resolve_movies', folder=False)
                end()
                setview('List')

@route('/find_series')
def find_series():
    keyboard = xbmc.Keyboard('', getString(32028))
    keyboard.doModal()
    if keyboard.isConfirmed():
        query = keyboard.getText()
        if query:
            results = imdb.IMDBScraper().search_series(query)
            if results:
                setcontent('tvshows')
                for serie_name, image, url, description, imdb_id, original_name in results:
                    addMenuItem({
                        'name': serie_name,
                        'description': description,
                        'iconimage': image,
                        'url': url,
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
                'fanart': image,
                'url': '',
                'imdbnumber': imdb_id,
                'movie_name': movie_name,
                'original_name': original_name,
                'playable': True
            }, destiny='/play_resolve_movies', folder=False)
        if end_ < len(all_items):
            addMenuItem({'name': getString(32012), 'page': page + 1}, destiny='/imdb_movies_250')
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
            addMenuItem({'name': getString(32012), 'page': page + 1}, destiny='/imdb_series_250')
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
                'fanart': image,
                'url': '',
                'imdbnumber': imdb_id,
                'movie_name': movie_name,
                'original_name': original_name,
                'playable': True
            }, destiny='/play_resolve_movies', folder=False)
        if end_ < len(all_items):
            addMenuItem({'name': getString(32012), 'page': page + 1}, destiny='/imdb_movies_popular')
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
            addMenuItem({'name': getString(32012), 'page': page + 1}, destiny='/imdb_series_popular')
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
        db.save_season_episodes(
            imdb_id=imdb_id,
            season=int(season),
            serie_name=serie_name,
            original_name=original_name,
            episodes_data=itens
        )
        
        setcontent('episodes')
        for episode_number, name, img, fanart, description in itens:
            name_full = '{}x{} {}'.format(season, episode_number, name)
            
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
                'season': int(season),
                'episode': int(episode_number),
                'tvshowtitle': serie_name,
                'mediatype': 'episode',
                'playable': True
            }, destiny='/play_resolve_series', folder=False)
        
        end()
        setview('List')

@route('/play_resolve_movies')
def play_resolve_movies(param):
    movie_name = param.get('movie_name', param.get('name', ''))
    iconimage = param.get('iconimage', '')
    fanart = param.get('fanart', '')
    imdb_number = param.get('imdbnumber', '')
    description = param.get('description', '')
    year = param.get('year', '')
    original_name = param.get('original_name', '')

    loading_manager.show()
    
    try:
        result = api_vod.VOD().movie(imdb_number)
        if result:
            loading_manager.set_phase2()
            stream = result

            url = stream.split('|')[0] if '|' in stream else stream
            headers = stream.split('|', 1)[1] if '|' in stream else ''

            is_direct_file = url.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm', '.ts'))

            play_item = xbmcgui.ListItem(path=url)
            play_item.setArt({'thumb': iconimage, 'icon': iconimage, 'fanart': fanart or iconimage})
            play_item.setContentLookup(False)

            if is_direct_file:
                play_item.setMimeType('video/mp4')
                if headers:
                    url_with_headers = f"{url}|{headers}&User-Agent=Mozilla/5.0Referer=https://google.com"
                    play_item.setPath(url_with_headers)
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

            notify(getString(32020))
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, play_item)
            loading_manager.close()
        else:
            loading_manager.force_close()
            notify(getString(32016))
    except Exception as e:
        loading_manager.force_close()
        notify(getString(32016))

@route('/play_resolve_series')
def play_resolve_series(param):
    serie_name = param.get('serie_name', '')
    original_name = param.get('original_name', '')
    season = param.get('season_num', '')
    episode = param.get('episode_num', '')
    episode_title = param.get('episode_title', '')
    iconimage = param.get('iconimage', '')
    fanart = param.get('fanart', '')
    imdb_number = param.get('imdbnumber', '')
    description = param.get('description', '')
    
    if not episode or not season:
        notify(getString(32021))
        return
    
    if not str(episode).isdigit() or not str(season).isdigit():
        notify(getString(32022))
        return
    
    current_episode_num = int(episode)
    season_num = int(season)
    
    if current_episode_num <= 0 or season_num <= 0:
        notify(getString(32022))
        return

    loading_manager.show()
    
    try:
        result = api_vod.VOD().tvshows(imdb_number, season_num, current_episode_num)
        if result:
            loading_manager.set_phase2()
            stream = result

            url = stream.split('|')[0] if '|' in stream else stream
            headers = stream.split('|', 1)[1] if '|' in stream else ''

            is_direct_file = url.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm', '.ts'))

            display_title = '{}x{} {}'.format(season_num, str(current_episode_num).zfill(2), episode_title) if episode_title else '{}x{}'.format(season_num, str(current_episode_num).zfill(2))
            playback_title = episode_title if episode_title else 'S{}E{}'.format(season_num, str(current_episode_num).zfill(2))

            play_item = xbmcgui.ListItem(path=url)
            play_item.setArt({'thumb': iconimage, 'icon': iconimage, 'fanart': fanart or iconimage})
            play_item.setContentLookup(False)

            if is_direct_file:
                play_item.setMimeType('video/mp4')
                if headers:
                    url_with_headers = f"{url}|{headers}&User-Agent=Mozilla/5.0Referer=https://google.com"
                    play_item.setPath(url_with_headers)
            else:
                play_item.setProperty('inputstream', 'inputstream.adaptive')
                play_item.setProperty('inputstream.adaptive.manifest_type', 'hls')
                play_item.setProperty('inputstream.adaptive.original_audio_language', 'pt')
                if headers:
                    play_item.setProperty('inputstream.adaptive.stream_headers', headers)

            kodi_version = int(xbmc.getInfoLabel('System.BuildVersion').split('.')[0])
            if kodi_version >= 20:
                info_tag = play_item.getVideoInfoTag()
                info_tag.setTitle(playback_title)
                info_tag.setTvShowTitle(serie_name)
                info_tag.setOriginalTitle(original_name)
                info_tag.setPlot(description)
                info_tag.setIMDBNumber(imdb_number)
                info_tag.setMediaType('episode')
                info_tag.setSeason(season_num)
                info_tag.setEpisode(current_episode_num)
            else:
                info_dict = {
                    'title': playback_title,
                    'tvshowtitle': serie_name,
                    'originaltitle': original_name,
                    'plot': description,
                    'imdbnumber': imdb_number,
                    'mediatype': 'episode',
                    'season': season_num,
                    'episode': current_episode_num,
                }
                play_item.setInfo('video', info_dict)

            notify(getString(32020))
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, play_item)
            loading_manager.close()
            
            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            current_position = playlist.getposition()
            
            if current_position == 0 or playlist.size() <= 1:
                all_episodes = db.get_season_episodes(imdb_number, season_num)
                if all_episodes:
                    build_series_playlist(
                        imdb_number=imdb_number,
                        season_num=season_num,
                        current_episode_num=current_episode_num,
                        serie_name=serie_name,
                        original_name=original_name,
                        all_episodes=all_episodes
                    )
            
            player = get_player()
            threading.Thread(
                target=player.start_monitoring,
                args=(imdb_number, season_num, current_episode_num),
                daemon=True
            ).start()
        else:
            loading_manager.force_close()
            notify(getString(32016))
    except Exception as e:
        loading_manager.force_close()
        notify(getString(32016))
