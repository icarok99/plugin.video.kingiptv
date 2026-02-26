# -*- coding: utf-8 -*-

import xbmc
import threading
from lib.upnext import UpNextService
from lib.skipservice import SkipService
from lib.database import KingDatabase

db = KingDatabase()

class KingPlayer(xbmc.Player):

    def __init__(self):
        super(KingPlayer, self).__init__()
        self.imdb_id = None
        self.season = None
        self.episode = None
        self._state_lock = threading.Lock()
        self._monitoring = False
        self._monitor_thread = None
        self._skip_service = SkipService(db)
        self._upnext_service = UpNextService(db)

    def start_monitoring(self, imdb_id, season, episode):
        with self._state_lock:
            self._monitoring = False

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=3.0)

        with self._state_lock:
            self.imdb_id = imdb_id
            self.season = season
            self.episode = episode
            self._monitoring = True

        self._monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(imdb_id, season, episode),
            daemon=True,
        )
        self._monitor_thread.start()

    def mark_skip_point(self, point):
        with self._state_lock:
            imdb_id = self.imdb_id
            season = self.season
            episode = self.episode
        if imdb_id and season is not None and episode is not None:
            self._skip_service.save_skip_point(imdb_id, season, episode, point)

    def _monitoring_loop(self, imdb_id, season, episode):
        monitor = xbmc.Monitor()

        waited = 0
        while waited < 30 and not monitor.abortRequested():
            if self.isPlayingVideo():
                break
            monitor.waitForAbort(0.5)
            waited += 0.5

        if not self.isPlayingVideo():
            with self._state_lock:
                self._monitoring = False
            return

        total_time = 0
        for _ in range(60):
            with self._state_lock:
                if not self._monitoring:
                    return
            try:
                total_time = self.getTotalTime()
                if total_time > 60:
                    break
            except Exception:
                pass
            monitor.waitForAbort(0.5)

        if total_time <= 60:
            with self._state_lock:
                self._monitoring = False
            return

        skip_data = self._skip_service.load(imdb_id, season, episode)
        next_info = self._upnext_service.load(imdb_id, season, episode)

        threading.Thread(
            target=self._skip_service.prefetch_season,
            args=(imdb_id, season),
            daemon=True,
        ).start()

        watched_at = total_time * 0.9
        upnext_start_at = min(
            total_time * 0.9,
            total_time - self._upnext_service.trigger_seconds - 30
        )
        watched_marked = False
        skip_shown = False
        upnext_shown = False

        intro_start = skip_data.get('intro_start') if skip_data else None
        intro_end = skip_data.get('intro_end') if skip_data else None

        while self.isPlayingVideo():
            with self._state_lock:
                if not self._monitoring:
                    break
            if monitor.abortRequested():
                break

            try:
                ct = self.getTime()
            except Exception:
                monitor.waitForAbort(0.5)
                continue

            if not skip_shown and intro_start is not None and intro_end is not None:
                if (intro_start - self._skip_service.tolerance) <= ct <= intro_end:
                    skip_shown = True
                    if self._skip_service.auto_skip:
                        try:
                            self.seekTime(intro_end)
                        except Exception:
                            pass
                    else:
                        threading.Thread(
                            target=self._skip_service.show_dialog,
                            args=(intro_end, skip_data.get('_ep_label', ''), skip_data.get('_thumbnail', '')),
                            daemon=True,
                        ).start()

            if ct < upnext_start_at:
                monitor.waitForAbort(0.5)
                continue

            if not watched_marked and ct >= watched_at:
                watched_marked = True
                with self._state_lock:
                    self._upnext_service._watched_marked = True
                threading.Thread(
                    target=db.mark_watched,
                    args=(imdb_id, season, episode),
                    daemon=True,
                ).start()

            if not upnext_shown and next_info:
                if (total_time - ct) <= self._upnext_service.trigger_seconds:
                    upnext_shown = True
                    threading.Thread(
                        target=self._upnext_service.show_dialog,
                        args=(next_info,),
                        daemon=True,
                    ).start()

            monitor.waitForAbort(0.5)

        with self._state_lock:
            self._monitoring = False

    def _on_stop(self):
        with self._state_lock:
            self._monitoring = False
            self._upnext_service._watched_marked = False
            self.imdb_id = None
            self.season = None
            self.episode = None

    def onPlayBackEnded(self):
        with self._state_lock:
            imdb_id = self.imdb_id
            season = self.season
            episode = self.episode
            already_marked = self._upnext_service._watched_marked
            self._monitoring = False
            self._upnext_service._watched_marked = False
            self.imdb_id = None
            self.season = None
            self.episode = None
        if imdb_id and season is not None and episode is not None and not already_marked:
            threading.Thread(
                target=db.mark_watched,
                args=(imdb_id, season, episode),
                daemon=True,
            ).start()

    def onPlayBackStopped(self):
        self._on_stop()

    def onPlayBackError(self):
        self._on_stop()

_global_player = None
_player_lock = threading.Lock()

def get_player():
    global _global_player
    with _player_lock:
        if _global_player is None:
            _global_player = KingPlayer()
        return _global_player
