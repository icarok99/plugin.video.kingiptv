# -*- coding: utf-8 -*-

import os
import threading
from lib.helper import *
import inputstreamhelper
from lib import xtream, tunein, pluto, trakt, api_vod, hlsretry

try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode

from lib.player import get_player
from lib.loading_window import loading_manager
from lib.skipservice import prefetch_skip_timestamps
from lib.db_manager import KingDatabaseManager

db_manager = KingDatabaseManager()
db_manager.check_auto_expiry()

from lib.database import KingDatabase

_db = None

def get_db():
    global _db
    if _db is None:
        _db = KingDatabase()
    return _db

_addon = xbmcaddon.Addon()

def getString(string_id):
    return _addon.getLocalizedString(string_id)

profile = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.kingiptv')

try:
    import github_update
    from datetime import datetime
    import requests

    UPDATE_CHECK_FILE = os.path.join(profile, 'last_checked_date.txt')
    REMOTE_DATE_URL   = 'https://raw.githubusercontent.com/icarok99-alt/plugin.video.kingiptv/main/last_update.txt'

    def get_local_date():
        if os.path.exists(UPDATE_CHECK_FILE):
            with open(UPDATE_CHECK_FILE, 'r') as f:
                content = f.read().strip()
                if content:
                    try:
                        return datetime.strptime(content, '%d-%m-%Y')
                    except ValueError:
                        pass
        return datetime.strptime('24-02-2026', '%d-%m-%Y')

    def save_local_date(date_str):
        with open(UPDATE_CHECK_FILE, 'w') as f:
            f.write(date_str)

    def is_update_needed_by_date():
        try:
            response = requests.get(REMOTE_DATE_URL, timeout=5)
            if response.status_code == 200:
                remote_date_str = response.text.strip()
                remote_date     = datetime.strptime(remote_date_str, '%d-%m-%Y')
                local_date      = get_local_date()
                if remote_date > local_date:
                    save_local_date(remote_date_str)
                    return True
        except Exception as e:
            print(f'Erro ao verificar data remota: {e}')
        return False

except Exception as e:
    from xbmcgui import Dialog
    Dialog().notification(getString(32026), str(e), xbmcgui.NOTIFICATION_ERROR, 5000)

TITULO       = '::: KING IPTV :::'
API_CHANNELS = '\x68\x74\x74\x70\x73\x3a\x2f\x2f\x64\x6f\x63\x73\x2e\x67\x6f\x6f\x67\x6c\x65\x2e\x63\x6f\x6d\x2f\x75\x63\x3f\x65\x78\x70\x6f\x72\x74\x3d\x64\x6f\x77\x6e\x6c\x6f\x61\x64\x26\x69\x64\x3d\x31\x67\x52\x53\x61\x72\x30\x49\x79\x32\x6f\x47\x65\x70\x4c\x33\x4c\x6b\x4d\x74\x43\x62\x77\x54\x7a\x67\x53\x67\x68\x41\x73\x77\x36'
API_RADIOS   = '\x68\x74\x74\x70\x73\x3a\x2f\x2f\x67\x69\x73\x74\x2e\x67\x69\x74\x68\x75\x62\x75\x73\x65\x72\x63\x6f\x6e\x74\x65\x6e\x74\x2e\x63\x6f\x6d\x2f\x69\x63\x61\x72\x6f\x6b\x39\x39\x2f\x64\x65\x38\x38\x63\x33\x66\x30\x61\x34\x31\x39\x64\x32\x35\x34\x30\x33\x62\x31\x31\x30\x65\x33\x64\x31\x32\x38\x37\x31\x65\x31\x2f\x72\x61\x77\x2f\x62\x65\x33\x32\x64\x65\x32\x37\x65\x63\x33\x36\x34\x39\x36\x30\x34\x37\x66\x30\x61\x33\x35\x64\x63\x31\x38\x65\x62\x34\x34\x65\x66\x37\x39\x65\x38\x66\x63\x33\x2f\x72\x61\x64\x69\x6f\x73\x2e\x6a\x73\x6f\x6e'

if not exists(profile):
    try:
        os.makedirs(profile)
    except OSError as e:
        if e.errno != 17:
            pass

IPTV_PROBLEM_LOG = translate(os.path.join(profile, 'iptv_problems_log.txt'))


# ═══════════════════════════════════════════════════════════════════════════
# Helpers internos de renderização
# ═══════════════════════════════════════════════════════════════════════════

def _movie_item(m):
    name, img, _url, desc, imdb_id, original_name, year, fanart = m
    return {
        'name':          '{} ({})'.format(name, year) if year and year != '0' else name,
        'description':   desc,
        'iconimage':     img,
        'fanart':        fanart or img,
        'imdbnumber':    imdb_id,
        'movie_name':    name,
        'original_name': original_name,
        'year':          year,
        'playable':      True,
    }


def _serie_item(s):
    name, img, slug, desc, imdb_id, original_name, year, fanart = s
    return {
        'name':          '{} ({})'.format(name, year) if year and year != '0' else name,
        'description':   desc,
        'iconimage':     img,
        'fanart':        fanart or img,
        'url':           slug,
        'imdbnumber':    imdb_id,
        'serie_name':    name,
        'original_name': original_name,
        'year':          year,
    }


def _render_movies(items, route, page):
    if not items:
        return
    setcontent('movies')
    for m in items:
        addMenuItem(_movie_item(m), destiny='/play_resolve_movies', folder=False)
    addMenuItem({'name': getString(32012), 'page': page + 1}, destiny=route)
    end()
    setview('List')


def _render_series(items, route, page):
    if not items:
        return
    setcontent('tvshows')
    for s in items:
        addMenuItem(_serie_item(s), destiny='/open_seasons')
    addMenuItem({'name': getString(32012), 'page': page + 1}, destiny=route)
    end()
    setview('List')


def _require_auth():
    if trakt.is_authenticated():
        return True
    xbmcgui.Dialog().ok(getString(32042), getString(32056))
    return False


# ═══════════════════════════════════════════════════════════════════════════
# Playlist automática de episódios
# ═══════════════════════════════════════════════════════════════════════════

def _build_series_playlist(imdb_number, season_num, current_ep,
                           serie_name, original_name, all_episodes):
    if not all_episodes or not isinstance(all_episodes, list):
        return
    playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    for ep in all_episodes:
        if not isinstance(ep, dict):
            continue
        ep_num = ep.get('episode')
        if not ep_num or ep_num <= current_ep:
            continue
        name   = ep.get('episode_title', '')
        img    = ep.get('thumbnail', '')
        fanart = ep.get('fanart', '')
        desc   = ep.get('description', '')
        params = {
            'serie_name': serie_name, 'original_name': original_name,
            'season_num': str(season_num), 'episode_num': str(ep_num),
            'episode_title': name, 'iconimage': img, 'fanart': fanart,
            'imdbnumber': imdb_number, 'description': desc,
        }
        plugin_url = 'plugin://plugin.video.kingiptv/play_resolve_series/{}'.format(
            urlencode(params))
        label = name if name else '{}x{}'.format(season_num, str(ep_num).zfill(2))
        li = xbmcgui.ListItem(label)
        li.setArt({'thumb': img, 'icon': img, 'fanart': fanart or img})
        kv = int(xbmc.getInfoLabel('System.BuildVersion').split('.')[0])
        if kv >= 20:
            tag = li.getVideoInfoTag()
            tag.setTitle(name); tag.setTvShowTitle(serie_name); tag.setPlot(desc)
            tag.setMediaType('episode'); tag.setSeason(season_num); tag.setEpisode(ep_num)
        else:
            li.setInfo('video', {
                'title': name, 'tvshowtitle': serie_name, 'plot': desc,
                'mediatype': 'episode', 'season': season_num, 'episode': ep_num,
            })
        playlist.add(url=plugin_url, listitem=li)


# ═══════════════════════════════════════════════════════════════════════════
# Menu principal
# ═══════════════════════════════════════════════════════════════════════════

@route('/')
def index():
    try:
        if is_update_needed_by_date():
            xbmcgui.Dialog().notification('KING IPTV', getString(32023), xbmcgui.NOTIFICATION_INFO, 5000)
            github_update.update_files()
            xbmcgui.Dialog().notification('KING IPTV', getString(32024), xbmcgui.NOTIFICATION_INFO, 5000)
    except Exception as e:
        xbmcgui.Dialog().notification('KING IPTV', '{}: {}'.format(getString(32026), e),
                                       xbmcgui.NOTIFICATION_ERROR, 5000)

    addMenuItem({'name': TITULO,           'description': ''}, destiny='')
    addMenuItem({'name': getString(32000), 'description': ''}, destiny='/playlistiptv')
    addMenuItem({'name': getString(32001), 'description': ''}, destiny='/channels_pluto')
    addMenuItem({'name': getString(32002), 'description': ''}, destiny='/radios')
    addMenuItem({'name': getString(32003), 'description': ''}, destiny='/menu_movies')
    addMenuItem({'name': getString(32004), 'description': ''}, destiny='/menu_series')
    addMenuItem({'name': getString(32005)}, destiny='/settings')
    end()
    setview('WideList')


# ═══════════════════════════════════════════════════════════════════════════
# Configurações
# ═══════════════════════════════════════════════════════════════════════════

@route('/settings')
def settings():
    xbmcaddon.Addon().openSettings()


# ═══════════════════════════════════════════════════════════════════════════
# IPTV
# ═══════════════════════════════════════════════════════════════════════════

@route('/playlistiptv')
def playlistiptv():
    iptv = xtream.parselist(API_CHANNELS)
    if iptv:
        for n, (dns, username, password) in enumerate(iptv, start=1):
            addMenuItem({'name': 'LISTA {}'.format(n), 'description': '',
                         'dns': dns, 'username': str(username), 'password': str(password)},
                        destiny='/cat_channels')
        end()
        setview('WideList')
    else:
        notify(getString(32013))


@route('/cat_channels')
def cat_channels(param):
    dns, username, password = param['dns'], param['username'], param['password']
    cat = xtream.API(dns, username, password).channels_category()
    if cat:
        for name, url in cat:
            addMenuItem({'name': name, 'description': '', 'dns': dns,
                         'username': username, 'password': password, 'url': url},
                        destiny='/open_channels')
        end()
        setview('WideList')
    else:
        url_problem = '{}/get.php?username={}&password={}\n'.format(dns, username, password)
        check = False
        if exists(IPTV_PROBLEM_LOG):
            with open(IPTV_PROBLEM_LOG, 'r') as f:
                check = url_problem in f.read()
        with open(IPTV_PROBLEM_LOG, 'a', encoding='utf-8') as f:
            if not check:
                f.write(url_problem)
        notify(getString(32014))


@route('/open_channels')
def open_channels(param):
    dns, username, password, url = (param['dns'], param['username'],
                                    param['password'], param['url'])
    items = xtream.API(dns, username, password).channels_open(url)
    if items:
        setcontent('videos')
        for name, link, thumb, desc in items:
            addMenuItem({'name': name, 'description': desc, 'iconimage': thumb, 'url': link},
                        destiny='/play_iptv', folder=False)
        end()
        setview('WideList')
    else:
        notify(getString(32015))


@route('/play_iptv')
def play_iptv(param):
    name      = param.get('name', getString(32029))
    desc      = param.get('description', '')
    iconimage = param.get('iconimage', '')
    url       = param.get('url', '').split('|')[0]
    try:
        hlsretry.XtreamProxy().start()
    except Exception:
        pass
    proxy = 'http://127.0.0.1:{}/?url={}'.format(hlsretry.PORT_NUMBER, quote_plus(url))
    li = xbmcgui.ListItem(path=proxy)
    li.setContentLookup(False)
    li.setArt({'icon': iconimage or 'DefaultVideo.png', 'thumb': iconimage or 'DefaultVideo.png'})
    li.setMimeType('application/vnd.apple.mpegurl')
    tag = li.getVideoInfoTag() if hasattr(li, 'getVideoInfoTag') else None
    if tag:
        tag.setTitle(name); tag.setPlot(desc); tag.setMediaType('video')
    else:
        li.setInfo('video', {'title': name, 'plot': desc})
    xbmc.Player().play(proxy, li)


# ═══════════════════════════════════════════════════════════════════════════
# Pluto TV
# ═══════════════════════════════════════════════════════════════════════════

@route('/channels_pluto')
def channels_pluto():
    channels = pluto.playlist_pluto()
    if channels:
        setcontent('videos')
        for name, desc, thumb, url in channels:
            addMenuItem({'name': name, 'description': desc, 'iconimage': thumb,
                         'url': url, 'playable': 'true'}, destiny='/play_pluto', folder=False)
        end()
        setview('List')
    else:
        notify(getString(32018))


@route('/play_pluto')
def play_pluto(param):
    url       = param.get('url', '')
    name      = param.get('name', '')
    iconimage = param.get('iconimage', '')
    desc      = param.get('description', '')
    if not url:
        notify(getString(32016))
        return
    helper = inputstreamhelper.Helper('hls')
    if not helper.check_inputstream():
        return
    headers = url.split('|')[1] if '|' in url else ''
    url     = url.split('|')[0] if '|' in url else url
    li = xbmcgui.ListItem(path=url)
    li.setProperty('inputstream', helper.inputstream_addon)
    li.setProperty('inputstream.adaptive.manifest_type', 'hls')
    li.setProperty('inputstream.adaptive.stream_headers',   headers or 'User-Agent=Mozilla/5.0')
    li.setProperty('inputstream.adaptive.manifest_headers', headers or 'User-Agent=Mozilla/5.0')
    li.setMimeType('application/x-mpegURL')
    li.setProperty('inputstream.adaptive.live_delay', '0')
    li.setProperty('inputstream.adaptive.manifest_update_parameter', 'full')
    li.setArt({'icon': iconimage or 'DefaultVideo.png', 'thumb': iconimage or 'DefaultVideo.png'})
    tag = li.getVideoInfoTag() if hasattr(li, 'getVideoInfoTag') else None
    if tag:
        tag.setTitle(name); tag.setPlot(desc); tag.setMediaType('video')
    else:
        li.setInfo('video', {'title': name, 'plot': desc})
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, li)


# ═══════════════════════════════════════════════════════════════════════════
# Rádios
# ═══════════════════════════════════════════════════════════════════════════

@route('/radios')
def radios():
    items = tunein.radios_list(API_RADIOS)
    if items:
        for name, url in items:
            addMenuItem({'name': name, 'url': url}, destiny='/play_radio')
        end()
        setview('List')


@route('/play_radio')
def play_radio(param):
    name = param.get('name', '')
    url  = param.get('url', '')
    if not url:
        return
    li = xbmcgui.ListItem(path=url)
    li.setContentLookup(False)
    li.setArt({'icon': 'DefaultAudio.png', 'thumb': 'DefaultAudio.png'})
    tag = li.getVideoInfoTag() if hasattr(li, 'getVideoInfoTag') else None
    if tag:
        tag.setTitle(name); tag.setMediaType('song')
    else:
        li.setInfo('music', {'title': name})
    xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, li)


# ═══════════════════════════════════════════════════════════════════════════
# Trakt — Conta
# ═══════════════════════════════════════════════════════════════════════════

@route('/trakt_account')
def trakt_account():
    addMenuItem({'name': getString(32057), 'description': ''}, destiny='/trakt_watchlist_movies')
    addMenuItem({'name': getString(32058), 'description': ''}, destiny='/trakt_watchlist_series')
    addMenuItem({'name': getString(32059), 'description': ''}, destiny='/trakt_rec_movies')
    addMenuItem({'name': getString(32060), 'description': ''}, destiny='/trakt_rec_series')
    addMenuItem({'name': getString(32061), 'description': ''}, destiny='/trakt_rated_movies')
    addMenuItem({'name': getString(32062), 'description': ''}, destiny='/trakt_rated_series')
    addMenuItem({'name': getString(32063), 'description': ''}, destiny='/trakt_history_movies')
    addMenuItem({'name': getString(32064), 'description': ''}, destiny='/trakt_history_series')
    addMenuItem({'name': getString(32045), 'description': ''}, destiny='/trakt_logout')
    end()
    setview('List')


@route('/trakt_logout')
def trakt_logout():
    if xbmcgui.Dialog().yesno(getString(32042), getString(32065)):
        trakt.revoke_auth()
        notify(getString(32054))
        xbmc.executebuiltin('Container.Refresh')


# ═══════════════════════════════════════════════════════════════════════════
# Menu Filmes
# ═══════════════════════════════════════════════════════════════════════════

@route('/menu_movies')
def menu_movies():
    addMenuItem({'name': getString(32006), 'description': ''}, destiny='/find_movies')
    addMenuItem({'name': getString(32007), 'description': ''}, destiny='/movies_popular')
    addMenuItem({'name': getString(32008), 'description': ''}, destiny='/movies_trending')
    if trakt.is_authenticated():
        addMenuItem({'name': getString(32057), 'description': ''}, destiny='/trakt_watchlist_movies')
        addMenuItem({'name': getString(32059), 'description': ''}, destiny='/trakt_rec_movies')
        addMenuItem({'name': getString(32061), 'description': ''}, destiny='/trakt_rated_movies')
        addMenuItem({'name': getString(32063), 'description': ''}, destiny='/trakt_history_movies')
    end()
    setview('List')


@route('/find_movies')
def find_movies():
    keyboard = xbmc.Keyboard('', getString(32027))
    keyboard.doModal()
    if not keyboard.isConfirmed() or not keyboard.getText():
        return
    results = trakt.search_movies(keyboard.getText())
    if not results:
        notify(getString(32016))
        return
    setcontent('movies')
    for m in results:
        addMenuItem(_movie_item(m), destiny='/play_resolve_movies', folder=False)
    end()
    setview('List')


@route('/movies_popular')
def movies_popular(param=None):
    page = int(param.get('page', 1)) if param else 1
    _render_movies(trakt.movies_popular(page=page), '/movies_popular', page)


@route('/movies_trending')
def movies_trending(param=None):
    page = int(param.get('page', 1)) if param else 1
    _render_movies(trakt.movies_trending(page=page), '/movies_trending', page)


@route('/trakt_watchlist_movies')
def trakt_watchlist_movies():
    if _require_auth():
        _render_movies(trakt.watchlist_movies(), '/trakt_watchlist_movies', 1)


@route('/trakt_rec_movies')
def trakt_rec_movies():
    if _require_auth():
        _render_movies(trakt.recommendations_movies(), '/trakt_rec_movies', 1)


@route('/trakt_rated_movies')
def trakt_rated_movies():
    if _require_auth():
        _render_movies(trakt.rated_movies(), '/trakt_rated_movies', 1)


@route('/trakt_history_movies')
def trakt_history_movies(param=None):
    if _require_auth():
        page = int(param.get('page', 1)) if param else 1
        _render_movies(trakt.history_movies(page=page), '/trakt_history_movies', page)


# ═══════════════════════════════════════════════════════════════════════════
# Menu Séries
# ═══════════════════════════════════════════════════════════════════════════

@route('/menu_series')
def menu_series():
    addMenuItem({'name': getString(32009), 'description': ''}, destiny='/find_series')
    addMenuItem({'name': getString(32010), 'description': ''}, destiny='/series_popular')
    addMenuItem({'name': getString(32011), 'description': ''}, destiny='/series_trending')
    if trakt.is_authenticated():
        addMenuItem({'name': getString(32058), 'description': ''}, destiny='/trakt_watchlist_series')
        addMenuItem({'name': getString(32060), 'description': ''}, destiny='/trakt_rec_series')
        addMenuItem({'name': getString(32062), 'description': ''}, destiny='/trakt_rated_series')
        addMenuItem({'name': getString(32064), 'description': ''}, destiny='/trakt_history_series')
    end()
    setview('List')


@route('/find_series')
def find_series():
    keyboard = xbmc.Keyboard('', getString(32028))
    keyboard.doModal()
    if not keyboard.isConfirmed() or not keyboard.getText():
        return
    results = trakt.search_series(keyboard.getText())
    if not results:
        notify(getString(32016))
        return
    setcontent('tvshows')
    for s in results:
        addMenuItem(_serie_item(s), destiny='/open_seasons')
    end()
    setview('List')


@route('/series_popular')
def series_popular(param=None):
    page = int(param.get('page', 1)) if param else 1
    _render_series(trakt.series_popular(page=page), '/series_popular', page)


@route('/series_trending')
def series_trending(param=None):
    page = int(param.get('page', 1)) if param else 1
    _render_series(trakt.series_trending(page=page), '/series_trending', page)


@route('/trakt_watchlist_series')
def trakt_watchlist_series():
    if _require_auth():
        _render_series(trakt.watchlist_series(), '/trakt_watchlist_series', 1)


@route('/trakt_rec_series')
def trakt_rec_series():
    if _require_auth():
        _render_series(trakt.recommendations_series(), '/trakt_rec_series', 1)


@route('/trakt_rated_series')
def trakt_rated_series():
    if _require_auth():
        _render_series(trakt.rated_series(), '/trakt_rated_series', 1)


@route('/trakt_history_series')
def trakt_history_series(param=None):
    if _require_auth():
        page = int(param.get('page', 1)) if param else 1
        _render_series(trakt.history_series(page=page), '/trakt_history_series', page)


# ═══════════════════════════════════════════════════════════════════════════
# Temporadas & Episódios
# ═══════════════════════════════════════════════════════════════════════════

@route('/open_seasons')
def open_seasons(param):
    serie_icon    = param.get('iconimage', '')
    serie_fanart  = param.get('fanart', '') or serie_icon
    serie_name    = param.get('serie_name', param.get('name', ''))
    original_name = param.get('original_name', '')
    url           = param.get('url', '')
    imdb_id       = param.get('imdbnumber', '')

    items = trakt.get_seasons(url)
    if not items:
        return
    setcontent('tvshows')
    for season_num, label, season_ref in items:
        addMenuItem({
            'name': label, 'description': '', 'iconimage': serie_icon,
            'fanart': serie_fanart, 'url': season_ref, 'imdbnumber': imdb_id,
            'season': season_num, 'serie_name': serie_name,
            'original_name': original_name,
        }, destiny='/open_episodes')
    end()
    setview('List')


@route('/open_episodes')
def open_episodes(param):
    serie_name    = param.get('serie_name', '')
    original_name = param.get('original_name', '')
    url           = param.get('url', '')
    imdb_id       = param.get('imdbnumber', '')
    season        = param.get('season', '')

    items = trakt.get_episodes(url)
    if not items:
        return

    get_db().save_season_episodes(
        imdb_id=imdb_id, season=int(season),
        serie_name=serie_name, original_name=original_name,
        episodes_data=items,
    )
    prefetch_skip_timestamps(
        imdb_id=imdb_id, season=int(season),
        episode_count=len(items), database=get_db(),
    )
    watched_set = get_db().get_watched_in_season(imdb_id, int(season))

    setcontent('episodes')
    for ep_num, name, img, fanart, desc in items:
        name_full = '{}x{} - {}'.format(season, str(ep_num).zfill(2), name)
        addMenuItem({
            'name': name_full, 'description': desc, 'iconimage': img,
            'fanart': fanart, 'imdbnumber': imdb_id, 'season_num': season,
            'episode_num': str(ep_num), 'serie_name': serie_name,
            'original_name': original_name, 'episode_title': name,
            'mediatype': 'episode', 'playable': True,
            'playcount': 1 if int(ep_num) in watched_set else 0,
        }, destiny='/play_resolve_series', folder=False)
    end()
    setview('List')


# ═══════════════════════════════════════════════════════════════════════════
# Playback — Filmes
# ═══════════════════════════════════════════════════════════════════════════

@route('/play_resolve_movies')
def play_resolve_movies(param):
    movie_name    = param.get('movie_name', param.get('name', ''))
    iconimage     = param.get('iconimage', '')
    fanart        = param.get('fanart', '')
    imdb_number   = param.get('imdbnumber', '')
    description   = param.get('description', '')
    year          = param.get('year', '')
    original_name = param.get('original_name', '')

    loading_manager.show(fanart_path=fanart or None)
    try:
        result = api_vod.VOD().movie(imdb_number)
        if not result:
            loading_manager.force_close(); notify(getString(32016)); return

        loading_manager.set_phase2()
        url     = result.split('|')[0] if '|' in result else result
        headers = result.split('|', 1)[1] if '|' in result else ''
        is_file = url.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm', '.ts'))

        li = xbmcgui.ListItem(path=url)
        li.setArt({'thumb': iconimage, 'icon': iconimage, 'fanart': fanart or iconimage})
        li.setContentLookup(False)
        if is_file:
            li.setMimeType('video/mp4')
            if headers:
                li.setPath(f'{url}|{headers}&User-Agent=Mozilla/5.0Referer=https://google.com')
        else:
            li.setProperty('inputstream', 'inputstream.adaptive')
            li.setProperty('inputstream.adaptive.manifest_type', 'hls')
            li.setProperty('inputstream.adaptive.original_audio_language', 'pt')
            if headers:
                li.setProperty('inputstream.adaptive.stream_headers', headers)

        kv = int(xbmc.getInfoLabel('System.BuildVersion').split('.')[0])
        if kv >= 20:
            tag = li.getVideoInfoTag()
            tag.setTitle(movie_name); tag.setPlot(description)
            tag.setIMDBNumber(imdb_number); tag.setMediaType('movie')
            tag.setOriginalTitle(original_name)
            if year: tag.setYear(int(year))
        else:
            d = {'title': movie_name, 'plot': description, 'imdbnumber': imdb_number,
                 'mediatype': 'movie', 'originaltitle': original_name}
            if year: d['year'] = int(year)
            li.setInfo('video', d)

        notify(getString(32020))
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, li)
        loading_manager.close()
    except Exception:
        loading_manager.force_close(); notify(getString(32016))


# ═══════════════════════════════════════════════════════════════════════════
# Playback — Séries
# ═══════════════════════════════════════════════════════════════════════════

@route('/play_resolve_series')
def play_resolve_series(param):
    serie_name    = param.get('serie_name', '')
    original_name = param.get('original_name', '')
    season        = param.get('season_num', '')
    episode       = param.get('episode_num', '')
    ep_title      = param.get('episode_title', '')
    iconimage     = param.get('iconimage', '')
    fanart        = param.get('fanart', '')
    imdb_number   = param.get('imdbnumber', '')
    description   = param.get('description', '')

    if not (episode and season and str(episode).isdigit() and str(season).isdigit()):
        notify(getString(32022)); return

    season_num = int(season)
    ep_num     = int(episode)
    if ep_num <= 0 or season_num <= 0:
        notify(getString(32022)); return

    loading_manager.show(fanart_path=fanart or None)
    try:
        result = api_vod.VOD().tvshows(imdb_number, season_num, ep_num)
        if not result:
            loading_manager.force_close(); notify(getString(32016)); return

        loading_manager.set_phase2()
        url     = result.split('|')[0] if '|' in result else result
        headers = result.split('|', 1)[1] if '|' in result else ''
        is_file = url.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm', '.ts'))

        li = xbmcgui.ListItem(label=ep_title, path=url)
        li.setArt({'thumb': iconimage, 'icon': iconimage, 'fanart': fanart or iconimage})
        li.setContentLookup(False)
        if is_file:
            li.setMimeType('video/mp4')
            if headers:
                li.setPath(f'{url}|{headers}&User-Agent=Mozilla/5.0Referer=https://google.com')
        else:
            li.setProperty('inputstream', 'inputstream.adaptive')
            li.setProperty('inputstream.adaptive.manifest_type', 'hls')
            li.setProperty('inputstream.adaptive.original_audio_language', 'pt')
            if headers:
                li.setProperty('inputstream.adaptive.stream_headers', headers)

        kv = int(xbmc.getInfoLabel('System.BuildVersion').split('.')[0])
        if kv >= 20:
            tag = li.getVideoInfoTag()
            tag.setTitle(ep_title); tag.setTvShowTitle(serie_name)
            tag.setOriginalTitle(original_name); tag.setPlot(description)
            tag.setIMDBNumber(imdb_number); tag.setMediaType('episode')
            tag.setSeason(season_num); tag.setEpisode(ep_num)
        else:
            li.setInfo('video', {
                'title': ep_title, 'tvshowtitle': serie_name,
                'originaltitle': original_name, 'plot': description,
                'imdbnumber': imdb_number, 'mediatype': 'episode',
                'season': season_num, 'episode': ep_num,
            })

        notify(getString(32020))
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, li)
        loading_manager.close()

        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        if playlist.getposition() == 0 or playlist.size() <= 1:
            all_eps = get_db().get_season_episodes(imdb_number, season_num)
            if all_eps:
                _build_series_playlist(imdb_number, season_num, ep_num,
                                       serie_name, original_name, all_eps)

        player = get_player()
        threading.Thread(target=player.start_monitoring,
                         args=(imdb_number, season_num, ep_num),
                         daemon=True).start()
    except Exception:
        loading_manager.force_close(); notify(getString(32016))