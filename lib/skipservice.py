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

    def _button_label(self, remaining=None):
        if remaining is not None:
            return _str(32202).format(remaining)
        return _str(32110)

    def _tag_label(self):
        return _str(32205)

    def onInit(self):
        try:
            self.getControl(self.BUTTON_SKIP).setLabel(self._button_label(self.countdown_seconds))

            try:
                self.getControl(self.LABEL_TAG).setLabel(self._tag_label())
            except Exception:
                pass

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
                self.getControl(self.BUTTON_SKIP).setLabel(self._button_label(remaining))
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

        elif action_id in (
            xbmcgui.ACTION_NAV_BACK,
            xbmcgui.ACTION_PREVIOUS_MENU,
            xbmcgui.ACTION_STOP,
        ):
            self._stop_countdown = True
            self.close()



class SkipService:

    TOLERANCE = 2.0

    def __init__(self, player, database):
        self.player = player
        self.db = database

        addon = xbmcaddon.Addon()

        self.intro_enabled = self._get_bool(addon, 'skip_intro_enabled', True)
        self.auto_skip = self._get_bool(addon, 'skip_auto_skip', False)
        self.countdown_seconds = self._get_int(addon, 'skip_countdown_seconds', 5)

        self._monitor_lock = threading.Lock()
        self._stop_monitoring = False
        self.monitoring = False
        self.monitor_thread = None

        self._shown = {}
        self._dialog_lock = threading.Lock()

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

    def start_monitoring(self, imdb_id, season, episode):
        if not self.intro_enabled:
            return

        with self._dialog_lock:
            self._shown = {'intro': False}

        with self._monitor_lock:
            self._stop_monitoring = True
            self.monitoring = False

        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=3.0)

        skip_info = self._resolve_timestamps(imdb_id, season, episode)

        if skip_info is not None:
            ep_label, thumbnail = self._resolve_episode_info(imdb_id, season, episode)
            skip_info['_ep_label'] = ep_label
            skip_info['_thumbnail'] = thumbnail

        self._trigger_season_prefetch(imdb_id, season)

        with self._monitor_lock:
            self._stop_monitoring = False
            self.monitoring = True

        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(imdb_id, season, episode, skip_info),
            daemon=True,
        )
        self.monitor_thread.start()

    def _trigger_season_prefetch(self, imdb_id, season):
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
                if title:
                    ep_label = '{}x{:02d} - {}'.format(int(season), int(episode), title)
                else:
                    ep_label = '{}x{:02d}'.format(int(season), int(episode))
                return ep_label, thumbnail
        except Exception:
            pass

        return '', ''

    def _resolve_timestamps(self, imdb_id, season, episode):
        try:
            timestamps = self.db.get_skip_timestamps(imdb_id, season, episode)
            if timestamps:
                return timestamps

            url = '{}?imdb_id={}&season={}&episode={}'.format(
                INTRODB_URL, imdb_id, season, episode
            )
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

    def _monitoring_loop(self, imdb_id, season, episode, skip_info):
        monitor = xbmc.Monitor()

        waited = 0
        while waited < 30:
            if self.player.isPlayingVideo():
                break
            if monitor.waitForAbort(0.5):
                with self._monitor_lock:
                    self.monitoring = False
                return
            waited += 0.5

        if not self.player.isPlayingVideo():
            with self._monitor_lock:
                self.monitoring = False
            return

        total_time = 0
        for _ in range(60):
            if self._stop_monitoring:
                with self._monitor_lock:
                    self.monitoring = False
                return
            try:
                total_time = self.player.getTotalTime()
                if total_time > 60:
                    break
            except Exception:
                pass
            monitor.waitForAbort(0.5)

        if total_time <= 60:
            with self._monitor_lock:
                self.monitoring = False
            return

        if not skip_info:
            with self._monitor_lock:
                self.monitoring = False
            return

        intro_start = skip_info.get('intro_start')
        intro_end = skip_info.get('intro_end')

        T = self.TOLERANCE

        while self.player.isPlayingVideo() and not self._stop_monitoring:
            try:
                ct = self.player.getTime()

                if self.intro_enabled and intro_start is not None and intro_end is not None:
                    if (intro_start - T) <= ct <= intro_end:
                        with self._dialog_lock:
                            if not self._shown.get('intro'):
                                self._shown['intro'] = True
                                if self.auto_skip:
                                    try:
                                        self.player.seekTime(intro_end)
                                    except Exception:
                                        pass
                                else:
                                    self._show_dialog(
                                        intro_end,
                                        skip_info.get('_ep_label', ''),
                                        skip_info.get('_thumbnail', ''),
                                    )

            except Exception:
                pass

            if monitor.waitForAbort(0.5):
                break

        with self._monitor_lock:
            self.monitoring = False

    def stop_monitoring(self):
        with self._monitor_lock:
            self._stop_monitoring = True
            self.monitoring = False

    def _show_dialog(self, seek_to, episode_label='', thumbnail=''):
        threading.Thread(
            target=self._show_dialog_blocking,
            args=(seek_to, episode_label, thumbnail),
            daemon=True,
        ).start()

    def _show_dialog_blocking(self, seek_to, episode_label='', thumbnail=''):
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

_skip_service = None
_skip_lock = threading.Lock()

def get_skip_service(player, database):
    global _skip_service
    with _skip_lock:
        if _skip_service is None:
            _skip_service = SkipService(player, database)
        return _skip_service


MAX_WORKERS = 5

_prefetched_seasons      = set()
_prefetched_seasons_lock = threading.Lock()

_prefetch_running      = set()
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

    t = threading.Thread(
        target=_prefetch_worker,
        args=(imdb_id, int(season), int(episode_count), database),
        daemon=True,
    )
    t.start()

def _fetch_one_episode(imdb_id, season, ep):
    import requests as _requests

    for attempt in range(3):
        try:
            url = '{}?imdb_id={}&season={}&episode={}'.format(
                INTRODB_URL, imdb_id, season, ep
            )
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
                    return (
                        ep,
                        float(seg.get('start_sec', 0)),
                        float(seg.get('end_sec',   0)),
                    )

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
                        source='api'
                    )
                except Exception:
                    pass

        with _prefetched_seasons_lock:
            _prefetched_seasons.add(key)

    finally:
        with _prefetch_running_lock:
            _prefetch_running.discard(key)
