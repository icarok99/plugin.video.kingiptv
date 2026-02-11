# -*- coding: utf-8 -*-

import xbmc
import xbmcgui
import xbmcaddon
import threading
from lib.database import KingDatabase
from lib.upnext import get_upnext_service

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')

db = KingDatabase()


class KingPlayer(xbmc.Player):
    
    def __init__(self):
        super(KingPlayer, self).__init__()
        self.player = xbmc.Player()
        
        self.imdb_id = None
        self.content_type = None
        self.season = None
        self.episode = None
        
        self._state_lock = threading.Lock()
        self._tracking_thread = None
        self._stop_tracking = False
        
        self.upnext_service = get_upnext_service(self, db)
    
    def start_playback(self, imdb_id, content_type, season=None, episode=None, **kwargs):
        if self.upnext_service:
            self.upnext_service.stop_monitoring()
            xbmc.sleep(500)
        
        with self._state_lock:
            self._stop_tracking = True
        
        if self._tracking_thread and self._tracking_thread.is_alive():
            self._tracking_thread.join(timeout=2.0)
        
        with self._state_lock:
            self.imdb_id = imdb_id
            self.content_type = content_type
            self.season = season
            self.episode = episode
            self._stop_tracking = False
        
        self._tracking_thread = threading.Thread(target=self._tracking_loop)
        self._tracking_thread.daemon = True
        self._tracking_thread.start()
    
    def _tracking_loop(self):
        monitor = xbmc.Monitor()
        
        waited = 0
        max_wait = 45
        
        while waited < max_wait:
            if monitor.waitForAbort(0.5):
                self._cleanup_tracking_state()
                return
            
            if self._stop_tracking:
                self._cleanup_tracking_state()
                return
            
            try:
                if self.isPlayingVideo() and self.getTotalTime() > 30:
                    break
            except:
                pass
            
            waited += 0.5
        
        if not self.isPlayingVideo():
            self._cleanup_tracking_state()
            return
        
        try:
            total = self.getTotalTime()
            if total <= 30:
                self._cleanup_tracking_state()
                return
        except Exception:
            self._cleanup_tracking_state()
            return
        
        with self._state_lock:
            should_start_upnext = (
                self.content_type == 'episode' and 
                self.season is not None and 
                self.episode is not None and 
                self.imdb_id is not None
            )
        
        if should_start_upnext:
            try:
                self.upnext_service.start_monitoring(self.imdb_id, self.season, self.episode)
            except Exception:
                pass
        
        while self.isPlayingVideo() and not self._stop_tracking:
            if monitor.waitForAbort(5):
                break
    
    def _cleanup_tracking_state(self):
        with self._state_lock:
            self._stop_tracking = False
        
        if self.upnext_service:
            self.upnext_service.stop_monitoring()
    
    def onPlayBackStopped(self):
        if self.upnext_service:
            self.upnext_service.stop_monitoring()
        
        with self._state_lock:
            self._stop_tracking = True
            self.imdb_id = None
            self.content_type = None
            self.season = None
            self.episode = None
    
    def onPlayBackEnded(self):
        if self.upnext_service:
            self.upnext_service.stop_monitoring()
        
        with self._state_lock:
            self._stop_tracking = True
            self.imdb_id = None
            self.content_type = None
            self.season = None
            self.episode = None
    
    def onPlayBackError(self):
        self._cleanup_tracking_state()


class Monitor(xbmc.Monitor):
    
    def __init__(self):
        super(Monitor, self).__init__()
        self.playbackerror = False
    
    def onNotification(self, sender, method, data):
        if method == 'Player.OnStop':
            self.playbackerror = True


_global_player = None
_player_lock = threading.Lock()


def get_player():
    global _global_player
    
    with _player_lock:
        if _global_player is None:
            _global_player = KingPlayer()
        return _global_player


def start_tracking_episode(imdb_id, season, episode, title='', thumbnail='', fanart='', 
                          description='', serie_name='', original_name=''):
    player = get_player()
    
    player.start_playback(
        imdb_id=imdb_id,
        content_type='episode',
        season=season,
        episode=episode,
        title=title,
        thumbnail=thumbnail,
        fanart=fanart,
        description=description,
        serie_name=serie_name,
        original_name=original_name
    )
    
    return player
