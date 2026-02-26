# -*- coding: utf-8 -*-

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import xbmc
import xbmcgui
import xbmcaddon

try:
    from lib.helper import requests
except Exception:
    import requests

_addon = xbmcaddon.Addon()
INTRODB_URL = 'https://api.introdb.app/segments'

def _str(string_id):
    return _addon.getLocalizedString(string_id)

class SkipDialog(xbmcgui.WindowXMLDialog):

    BUTTON_SKIP = 4001
    BUTTON_CANCEL = 4002
    PROGRESS_BAR = 4004
    LABEL_TAG = 4005
    LABEL_EP = 4006
    IMAGE_THUMB = 4007

    def __init__(self, *args, **kwargs):
        self.seek_to = kwargs.get('seek_to', 0.0)
        self.countdown_seconds = kwargs.get('countdown_seconds', 5)
        self.episode_label = kwargs.get('episode_label', '')
        self.thumbnail = kwargs.get('thumbnail', '')
        self._stop_countdown = False
        self._countdown_thread = None
        self._player = xbmc.Player()

    def _do_seek(self):
        try:
            self._player.seekTime(self.seek_to)
        except Exception:
            pass

    def onInit(self):
        try:
            self.getControl(self.BUTTON_SKIP).setLabel(_str(32202).format(self.countdown_seconds))
            if self.episode_label:
                try:
                    self.getControl(self.LABEL_EP).setLabel(self.episode_label)
                except Exception:
                    pass
            if self.thumbnail:
                try:
                    self.getControl(self.IMAGE_THUMB).setImage(self.thumbnail)
                except Exception:
                    pass
            try:
                self.setFocusId(self.BUTTON_SKIP)
            except Exception:
                pass
            self._start_countdown()
        except Exception:
            pass

    def _start_countdown(self):
        self._stop_countdown = False
        self._countdown_thread = threading.Thread(target=self._countdown_loop, daemon=True)
        self._countdown_thread.start()

    def _countdown_loop(self):
        remaining = self.countdown_seconds
        while remaining > 0 and not self._stop_countdown:
            try:
                progress = int((remaining / float(self.countdown_seconds)) * 100)
                self.getControl(self.PROGRESS_BAR).setPercent(progress)
                self.getControl(self.BUTTON_SKIP).setLabel(_str(32202).format(remaining))
            except Exception:
                break
            time.sleep(1)
            remaining -= 1
        if not self._stop_countdown and remaining == 0:
            self._do_seek()
            self.close()

    def onClick(self, controlId):
        if controlId == self.BUTTON_SKIP:
            self._stop_countdown = True
            self._do_seek()
            self.close()
        elif controlId == self.BUTTON_CANCEL:
            self._stop_countdown = True
            self.close()

    def onAction(self, action):
        action_id = action.getId()
        if action_id in (xbmcgui.ACTION_SELECT_ITEM, xbmcgui.ACTION_PLAYER_PLAY):
            try:
                focused = self.getFocusId()
                if focused == self.BUTTON_SKIP:
                    self._stop_countdown = True
                    self._do_seek()
                    self.close()
                elif focused == self.BUTTON_CANCEL:
                    self._stop_countdown = True
                    self.close()
            except Exception:
                pass
        elif action_id in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_STOP):
            self._stop_countdown = True
            self.close()

class SkipService:

    def __init__(self, database):
        self.db = database
        addon = xbmcaddon.Addon()
        self.enabled = self._get_bool(addon, 'skip_intro_enabled', True)
        self.auto_skip = self._get_bool(addon, 'skip_auto_skip', False)
        self.countdown_seconds = self._get_int(addon, 'skip_countdown_seconds', 5)
        self.tolerance = 2.0

    @staticmethod
    def _get_bool(addon, key, default):
        try:
            return addon.getSettingBool(key)
        except Exception:
            val = addon.getSetting(key)
            return default if val == '' else val.lower() == 'true'

    @staticmethod
    def _get_int(addon, key, default):
        try:
            v = addon.getSettingInt(key)
            return v if v > 0 else default
        except Exception:
            try:
                return int(addon.getSetting(key)) or default
            except Exception:
                return default

    def load(self, imdb_id, season, episode):
        if not self.enabled:
            return {}
        skip_info = self._resolve_timestamps(imdb_id, season, episode)
        if skip_info:
            ep_label, thumbnail = self._resolve_episode_info(imdb_id, season, episode)
            skip_info['_ep_label'] = ep_label
            skip_info['_thumbnail'] = thumbnail
        return skip_info or {}

    def save_skip_point(self, imdb_id, season, episode, point):
        try:
            self.db.save_skip_point(imdb_id, season, episode, point)
        except Exception:
            pass

    def show_dialog(self, seek_to, episode_label='', thumbnail=''):
        try:
            addon = xbmcaddon.Addon()
            dialog = SkipDialog(
                'skip-dialog.xml',
                addon.getAddonInfo('path'),
                'default',
                '1080i',
                seek_to=seek_to,
                countdown_seconds=self.countdown_seconds,
                episode_label=episode_label,
                thumbnail=thumbnail,
            )
            dialog.doModal()
            del dialog
        except Exception:
            pass

    def prefetch_season(self, imdb_id, season):
        try:
            episodes = self.db.get_season_episodes(imdb_id, season)
            episode_count = len(episodes) if episodes else 0
            prefetch_skip_timestamps(imdb_id, season, episode_count, self.db)
        except Exception:
            pass

    def _resolve_episode_info(self, imdb_id, season, episode):
        try:
            meta = self.db.get_episode_metadata(imdb_id, int(season), int(episode))
            if meta:
                title = meta.get('episode_title') or ''
                thumbnail = meta.get('thumbnail') or ''
                ep_label = (
                    '{}x{:02d} - {}'.format(int(season), int(episode), title)
                    if title
                    else '{}x{:02d}'.format(int(season), int(episode))
                )
                return ep_label, thumbnail
        except Exception:
            pass
        return '', ''

    def _resolve_timestamps(self, imdb_id, season, episode):
        try:
            timestamps = self.db.get_skip_timestamps(imdb_id, season, episode)
            if timestamps:
                return timestamps
            url = '{}?imdb_id={}&season={}&episode={}'.format(INTRODB_URL, imdb_id, season, episode)
            import requests as _requests
            response = _requests.get(url, timeout=6)
            if response.status_code == 200:
                data = response.json()
                timestamps = {}
                seg = data.get('intro')
                if seg:
                    timestamps['intro_start'] = float(seg.get('start_sec', 0))
                    timestamps['intro_end'] = float(seg.get('end_sec', 0))
                if timestamps:
                    timestamps['source'] = 'api'
                    self.db.save_skip_timestamps(imdb_id, season, episode, **timestamps)
                    return timestamps
        except Exception:
            pass
        return {}

MAX_WORKERS = 5
_prefetched_seasons = set()
_prefetched_seasons_lock = threading.Lock()
_prefetch_running = set()
_prefetch_running_lock = threading.Lock()

def prefetch_skip_timestamps(imdb_id, season, episode_count, database):
    if not imdb_id or not season:
        return
    key = (imdb_id, int(season))
    with _prefetched_seasons_lock:
        if key in _prefetched_seasons:
            return
    with _prefetch_running_lock:
        if key in _prefetch_running:
            return
        _prefetch_running.add(key)
    threading.Thread(
        target=_prefetch_worker,
        args=(imdb_id, int(season), int(episode_count), database),
        daemon=True,
    ).start()

def _fetch_one_episode(imdb_id, season, ep):
    import requests as _requests
    for attempt in range(3):
        try:
            url = '{}?imdb_id={}&season={}&episode={}'.format(INTRODB_URL, imdb_id, season, ep)
            response = _requests.get(url, timeout=8)
            if response.status_code == 429:
                time.sleep(10 * (attempt + 1))
                continue
            if response.status_code == 200:
                try:
                    data = response.json()
                except Exception:
                    return (ep, None, None)
                seg = data.get('intro')
                if seg:
                    return (ep, float(seg.get('start_sec', 0)), float(seg.get('end_sec', 0)))
                return (ep, None, None)
            return (ep, None, None)
        except Exception:
            time.sleep(2)
    return (ep, None, None)

def _prefetch_worker(imdb_id, season, episode_count, database):
    key = (imdb_id, season)
    try:
        if episode_count > 0:
            candidates = list(range(1, episode_count + 1))
        else:
            try:
                rows = database.get_season_episodes(imdb_id, season)
                candidates = [r['episode'] for r in rows] if rows else []
            except Exception:
                candidates = []
        if not candidates:
            return
        pending = []
        for ep in candidates:
            try:
                already_checked = database.skip_timestamps_checked(imdb_id, season, ep)
            except Exception:
                already_checked = False
            if not already_checked:
                pending.append(ep)
        if not pending:
            return
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(_fetch_one_episode, imdb_id, season, ep): ep
                for ep in pending
            }
            for future in as_completed(futures):
                try:
                    ep, intro_start, intro_end = future.result()
                except Exception:
                    continue
                try:
                    database.save_skip_timestamps(
                        imdb_id, season, ep,
                        intro_start=intro_start,
                        intro_end=intro_end,
                        source='api',
                    )
                except Exception:
                    pass
        with _prefetched_seasons_lock:
            _prefetched_seasons.add(key)
    finally:
        with _prefetch_running_lock:
            _prefetch_running.discard(key)
