# -*- coding: utf-8 -*-

import xbmc
import threading
from lib.upnext import get_upnext_service
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

        self.upnext_service = get_upnext_service(self, db)

    def start_monitoring(self, imdb_id, season, episode):
        with self._state_lock:
            self.imdb_id = imdb_id
            self.season = season
            self.episode = episode
            self._monitoring = True

        monitor = xbmc.Monitor()
        waited = 0
        max_wait = 30

        while waited < max_wait and not monitor.abortRequested():
            if self.isPlayingVideo() and self.getTotalTime() > 30:
                break
            monitor.waitForAbort(0.5)
            waited += 0.5

        if self.isPlayingVideo() and self._monitoring:
            self.upnext_service.start_monitoring(self.imdb_id, self.season, self.episode)

    def onPlayBackEnded(self):
        with self._state_lock:
            imdb_id = self.imdb_id
            season  = self.season
            episode = self.episode
            self._monitoring = False
            self.imdb_id = None
            self.season = None
            self.episode = None
        already_marked = (
            self.upnext_service and
            self.upnext_service._watched_marked
        )

        if imdb_id and season is not None and episode is not None and not already_marked:
            threading.Thread(
                target=db.mark_watched,
                args=(imdb_id, season, episode),
                daemon=True
            ).start()

        if self.upnext_service:
            self.upnext_service.stop_monitoring()

    def onPlayBackStopped(self):
        with self._state_lock:
            self._monitoring = False
            self.imdb_id = None
            self.season = None
            self.episode = None

        if self.upnext_service:
            self.upnext_service.stop_monitoring()

    def onPlayBackError(self):
        with self._state_lock:
            self._monitoring = False

        if self.upnext_service:
            self.upnext_service.stop_monitoring()

_global_player = None
_player_lock = threading.Lock()

def get_player():
    global _global_player
    with _player_lock:
        if _global_player is None:
            _global_player = KingPlayer()
        return _global_player
