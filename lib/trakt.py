# -*- coding: utf-8 -*-
import os
import re
import json
import time
import html
import threading

try:
    from lib.helper import requests
except Exception:
    from helper import requests

try:
    import xbmc
    import xbmcgui
    import xbmcaddon
    import xbmcvfs
    _KODI = True
except ImportError:
    _KODI = False

TRAKT_CLIENT_ID     = 'e89e30a41bea868c945c33a704277903ee3f9c1e1a2b4daff09be5d4544e04c7'
TRAKT_CLIENT_SECRET = ''
TRAKT_BASE          = 'https://api.trakt.tv'

_BASE_HEADERS = {
    'Content-Type':      'application/json',
    'trakt-api-version': '2',
    'trakt-api-key':     TRAKT_CLIENT_ID,
}

_img_cache = {}

def _trakt_images(media_type, trakt_item):
    if not trakt_item or 'images' not in trakt_item:
        return '', ''

    trakt_id = trakt_item.get('ids', {}).get('trakt')
    if trakt_id:
        cache_key = f'{media_type}:{trakt_id}'
        if cache_key in _img_cache:
            return _img_cache[cache_key]

    images = trakt_item.get('images', {})

    poster = ''
    poster_list = images.get('poster') or []
    if poster_list:
        p = poster_list[0]
        poster = f"https://{p}" if not p.startswith('http') else p

    fanart = ''
    fanart_list = images.get('fanart') or []
    if fanart_list:
        f = fanart_list[0]
        fanart = f"https://{f}" if not f.startswith('http') else f

    result = (poster, fanart)

    if trakt_id:
        _img_cache[f'{media_type}:{trakt_id}'] = result

    return result

def _token_path():
    try:
        profile = xbmcvfs.translatePath(
            xbmcaddon.Addon('plugin.video.kingiptv').getAddonInfo('profile')
        )
        return os.path.join(profile, 'trakt_token.json')
    except Exception:
        return os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', 'userdata', 'trakt_token.json'
        )

def load_token():
    try:
        with open(_token_path(), 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_token(data):
    try:
        path = _token_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def delete_token():
    try:
        os.remove(_token_path())
    except Exception:
        pass

def _refresh_access_token(refresh_token):
    if not refresh_token or not TRAKT_CLIENT_SECRET:
        return None
    try:
        r = requests.post(
            TRAKT_BASE + '/oauth/token',
            headers={'Content-Type': 'application/json'},
            json={
                'refresh_token': refresh_token,
                'client_id':     TRAKT_CLIENT_ID,
                'client_secret': TRAKT_CLIENT_SECRET,
                'redirect_uri':  'urn:ietf:wg:oauth:2.0:oob',
                'grant_type':    'refresh_token',
            }
        )
        if r.status_code == 200:
            data = r.json()
            data['expires_at'] = time.time() + data.get('expires_in', 7776000)
            save_token(data)
            return data
    except Exception:
        pass
    return None

def get_access_token():
    tok = load_token()
    if not tok or not tok.get('access_token'):
        return None
    expires_at = tok.get('expires_at', 0)
    if expires_at and time.time() > expires_at - 604800:
        refreshed = _refresh_access_token(tok.get('refresh_token', ''))
        return refreshed.get('access_token') if refreshed else None
    return tok.get('access_token')

def is_authenticated():
    return bool(get_access_token())

def get_username():
    return load_token().get('username', '')

def _start_device_auth():
    try:
        r = requests.post(
            TRAKT_BASE + '/oauth/device/code',
            headers=_BASE_HEADERS,
            json={'client_id': TRAKT_CLIENT_ID}
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def _poll_device_token(device_code, interval=5, expires_in=600, on_success=None, on_pending=None, stop_event=None):
    if not TRAKT_CLIENT_SECRET:
        return False

    current_interval = interval
    deadline = time.time() + expires_in

    while time.time() < deadline:
        if stop_event and stop_event.is_set():
            return False

        time.sleep(current_interval)

        try:
            r = requests.post(
                TRAKT_BASE + '/oauth/device/token',
                headers=_BASE_HEADERS,
                json={
                    'code':          device_code,
                    'client_id':     TRAKT_CLIENT_ID,
                    'client_secret': TRAKT_CLIENT_SECRET,
                }
            )
            if r.status_code == 200:
                data = r.json()
                data['expires_at'] = time.time() + data.get('expires_in', 7776000)
                save_token(data)
                if on_success:
                    on_success(data)
                return True
            elif r.status_code == 400:
                if on_pending:
                    on_pending()
            elif r.status_code == 429:
                current_interval += 5
            elif r.status_code in (404, 409, 410, 418):
                break
        except Exception:
            pass

    return False

def ensure_auth():
    if is_authenticated():
        return True

    if not _KODI:
        return False

    addon = xbmcaddon.Addon('plugin.video.kingiptv')
    T     = addon.getLocalizedString

    auth_data = _start_device_auth()
    if not auth_data:
        xbmcgui.Dialog().notification('Trakt', T(32053), xbmcgui.NOTIFICATION_ERROR, 4000)
        return False

    user_code   = auth_data.get('user_code', '')
    verify_url  = auth_data.get('verification_url', 'https://trakt.tv/activate')
    device_code = auth_data.get('device_code', '')
    interval    = auth_data.get('interval', 5)
    expires_in  = auth_data.get('expires_in', 600)

    xbmcgui.Dialog().ok('Trakt', T(32049).format(verify_url, user_code))

    progress   = xbmcgui.DialogProgress()
    result     = [False]
    stop_event = threading.Event()

    def on_success(_):
        result[0] = True
        stop_event.set()

    threading.Thread(
        target=_poll_device_token,
        kwargs=dict(
            device_code=device_code,
            interval=interval,
            expires_in=expires_in,
            on_success=on_success,
            stop_event=stop_event,
        ),
        daemon=True
    ).start()

    progress.create('Trakt', T(32051))
    elapsed = 0
    while not stop_event.is_set() and elapsed < expires_in:
        if progress.iscanceled():
            stop_event.set()
            break
        xbmc.sleep(1000)
        elapsed += 1
        progress.update(int(elapsed * 100 / expires_in), T(32051))
    progress.close()

    if result[0]:
        xbmcgui.Dialog().notification(
            'Trakt', T(32052).format(get_username() or 'Trakt'),
            xbmcgui.NOTIFICATION_INFO, 4000
        )
        return True

    if not progress.iscanceled():
        xbmcgui.Dialog().notification('Trakt', T(32053), xbmcgui.NOTIFICATION_ERROR, 4000)
    return False

def revoke_auth():
    tok = load_token()
    if tok.get('access_token'):
        try:
            requests.post(
                TRAKT_BASE + '/oauth/revoke',
                headers=_BASE_HEADERS,
                json={
                    'token':         tok['access_token'],
                    'client_id':     TRAKT_CLIENT_ID,
                    'client_secret': TRAKT_CLIENT_SECRET,
                }
            )
        except Exception:
            pass
    delete_token()

def _get(path, params=None, auth=False):
    headers = dict(_BASE_HEADERS)
    if auth:
        token = get_access_token()
        if token:
            headers['Authorization'] = f'Bearer {token}'

    p = params or {}
    if 'extended' not in p:
        p['extended'] = 'images'

    try:
        r = requests.get(
            TRAKT_BASE + path,
            headers=headers,
            params=p,
            timeout=10
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def _slug_from(v):
    if '::' in v:
        v = v.split('::', 1)[0]
    m = re.search(r'/(tt\d+)/', v)
    return m.group(1) if m else v

def _to_movie(d):
    title   = html.unescape(str(d.get('title', '')).strip())
    year    = str(d.get('year', '') or '')
    desc    = html.unescape(str(d.get('overview', '') or ''))
    ids     = d.get('ids', {})
    imdb_id = ids.get('imdb', '') or ''
    slug    = ids.get('slug', '') or imdb_id
    poster, fanart = _trakt_images('movie', d)
    return (title, poster, slug, desc, imdb_id, title, year, fanart)

def _to_show(d):
    title   = html.unescape(str(d.get('title', '')).strip())
    year    = str(d.get('year', '') or '')
    desc    = html.unescape(str(d.get('overview', '') or ''))
    ids     = d.get('ids', {})
    imdb_id = ids.get('imdb', '') or ''
    slug    = ids.get('slug', '') or imdb_id
    poster, fanart = _trakt_images('show', d)
    return (title, poster, slug, desc, imdb_id, title, year, fanart)

def _valid(t):
    return bool(t[0] and t[2])

def _sort_search(results, key, query):
    q = query.strip().lower()
    def rank(item):
        trakt_score = item.get('score', 0) or 0
        title = str((item.get(key) or {}).get('title', '')).lower()
        return (title == q, title.startswith(q), trakt_score)
    return sorted(results, key=rank, reverse=True)

def search_movies(query):
    out = []
    try:
        raw = _get('/search/movie', {'query': query, 'limit': 30, 'extended': 'images'}) or []
        for r in _sort_search(raw, 'movie', query):
            t = _to_movie(r.get('movie', {}))
            if _valid(t):
                out.append(t)
    except Exception:
        pass
    return out

def search_series(query):
    out = []
    try:
        raw = _get('/search/show', {'query': query, 'limit': 30, 'extended': 'images'}) or []
        for r in _sort_search(raw, 'show', query):
            t = _to_show(r.get('show', {}))
            if _valid(t):
                out.append(t)
    except Exception:
        pass
    return out

def movies_popular(page=1, per_page=50):
    out = []
    try:
        for m in (_get('/movies/popular', {'limit': per_page, 'page': page}) or []):
            t = _to_movie(m)
            if _valid(t):
                out.append(t)
    except Exception:
        pass
    return out

def movies_trending(page=1, per_page=50):
    out = []
    try:
        for item in (_get('/movies/trending', {'limit': per_page, 'page': page}) or []):
            t = _to_movie(item.get('movie', {}))
            if _valid(t):
                out.append(t)
    except Exception:
        pass
    return out

def series_popular(page=1, per_page=50):
    out = []
    try:
        for s in (_get('/shows/popular', {'limit': per_page, 'page': page}) or []):
            t = _to_show(s)
            if _valid(t):
                out.append(t)
    except Exception:
        pass
    return out

def series_trending(page=1, per_page=50):
    out = []
    try:
        for item in (_get('/shows/trending', {'limit': per_page, 'page': page}) or []):
            t = _to_show(item.get('show', {}))
            if _valid(t):
                out.append(t)
    except Exception:
        pass
    return out

def watchlist_movies(sort='rank'):
    if not ensure_auth(): return []
    out = []
    try:
        for item in (_get('/users/me/watchlist/movies', {'sort': sort}, auth=True) or []):
            t = _to_movie(item.get('movie', {}))
            if _valid(t): out.append(t)
    except Exception:
        pass
    return out

def recommendations_movies(limit=40):
    if not ensure_auth(): return []
    out = []
    try:
        for m in (_get('/recommendations/movies', {'limit': limit, 'ignore_collected': 'true'}, auth=True) or []):
            t = _to_movie(m)
            if _valid(t): out.append(t)
    except Exception:
        pass
    return out

def rated_movies(rating=None):
    if not ensure_auth(): return []
    path = f'/users/me/ratings/movies/{rating}' if rating else '/users/me/ratings/movies'
    out  = []
    try:
        for item in (_get(path, auth=True) or []):
            t = _to_movie(item.get('movie', {}))
            if _valid(t): out.append(t)
    except Exception:
        pass
    return out

def history_movies(page=1, per_page=50):
    if not ensure_auth(): return []
    out = []
    try:
        for item in (_get('/users/me/history/movies', {'page': page, 'limit': per_page}, auth=True) or []):
            t = _to_movie(item.get('movie', {}))
            if _valid(t): out.append(t)
    except Exception:
        pass
    return out

def watchlist_series(sort='rank'):
    if not ensure_auth(): return []
    out = []
    try:
        for item in (_get('/users/me/watchlist/shows', {'sort': sort}, auth=True) or []):
            t = _to_show(item.get('show', {}))
            if _valid(t): out.append(t)
    except Exception:
        pass
    return out

def recommendations_series(limit=40):
    if not ensure_auth(): return []
    out = []
    try:
        for s in (_get('/recommendations/shows', {'limit': limit, 'ignore_collected': 'true'}, auth=True) or []):
            t = _to_show(s)
            if _valid(t): out.append(t)
    except Exception:
        pass
    return out

def rated_series(rating=None):
    if not ensure_auth(): return []
    path = f'/users/me/ratings/shows/{rating}' if rating else '/users/me/ratings/shows'
    out  = []
    try:
        for item in (_get(path, auth=True) or []):
            t = _to_show(item.get('show', {}))
            if _valid(t): out.append(t)
    except Exception:
        pass
    return out

def history_series(page=1, per_page=50):
    if not ensure_auth(): return []
    out  = []
    seen = set()
    try:
        for item in (_get('/users/me/history/shows', {'page': page, 'limit': per_page}, auth=True) or []):
            t = _to_show(item.get('show', {}))
            if _valid(t) and t[2] not in seen:
                seen.add(t[2])
                out.append(t)
    except Exception:
        pass
    return out

def get_seasons(slug_or_url):
    out = []
    try:
        slug = _slug_from(slug_or_url)
        for s in (_get(f'/shows/{slug}/seasons', {'extended': 'full,images'}) or []):
            num = s.get('number', 0)
            if num == 0:
                continue
            out.append((str(num), f'Season {num}', f'{slug}::{num}'))
    except Exception:
        pass
    return out

def get_episodes(season_ref):
    out = []
    try:
        slug, snum = season_ref.split('::', 1)
        show = _get(f'/shows/{slug}', {'extended': 'images'}) or {}
        poster, fanart = _trakt_images('show', show)

        for ep in (_get(f'/shows/{slug}/seasons/{snum}/episodes', {'extended': 'full'}) or []):
            num   = ep.get('number', 0)
            title = html.unescape(str(ep.get('title') or f'Episode {num}').strip())
            desc  = html.unescape(str(ep.get('overview', '') or ''))
            out.append((str(num), title, poster, fanart or poster, desc))
    except Exception:
        pass
    return out