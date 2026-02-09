# -*- coding: utf-8 -*-

import xbmc
import xbmcgui
import xbmcaddon
import json
import threading
from datetime import datetime
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
        self.current_time = 0
        self.total_time = 0
        self.is_tracking = False
        
        self.title = None
        self.season = None
        self.episode = None
        self.thumbnail = None
        self.fanart = None
        self.description = None
        self.serie_name = None
        self.original_name = None
        
        self._monitor = None
        self._tracking_thread = None
        self._stop_tracking = False
        self._saved_at_90_percent = False
        
        self._save_lock = threading.Lock()
        self._state_lock = threading.Lock()
        
        self.upnext_service = get_upnext_service(self, db)
    
    def start_playback(self, imdb_id, content_type, title, season=None, episode=None,
                      thumbnail='', fanart='', description='',
                      serie_name='', original_name=''):
        
        if self.upnext_service:
            self.upnext_service.stop_monitoring()
            xbmc.sleep(500)
        
        with self._state_lock:
            if self.is_tracking:
                self._stop_tracking = True
                self.is_tracking = False
        
        if self._tracking_thread and self._tracking_thread.is_alive():
            self._tracking_thread.join(timeout=2.0)
        
        with self._state_lock:
            self.imdb_id = imdb_id
            self.content_type = content_type
            self.title = title
            self.season = season
            self.episode = episode
            self.thumbnail = thumbnail
            self.fanart = fanart
            self.description = description
            self.serie_name = serie_name
            self.original_name = original_name
            self.is_tracking = True
            self._stop_tracking = False
            self._saved_at_90_percent = False
        
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
            
            self.total_time = int(total)
            
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
        
        self.current_time = 0
        
        while self.is_tracking and self.isPlayingVideo() and not self._stop_tracking:
            try:
                self.current_time = self.getTime()
                watched_percent = self.get_watched_percent()
                
                if watched_percent >= 90.0 and not self._saved_at_90_percent:
                    self._save_progress()
                    self._saved_at_90_percent = True
                
                if monitor.waitForAbort(2):
                    break
                    
            except Exception:
                break
        
        if not self._saved_at_90_percent:
            self._save_progress()
    
    def _cleanup_tracking_state(self):
        with self._state_lock:
            self.is_tracking = False
            self._stop_tracking = False
        
        if self.upnext_service:
            self.upnext_service.stop_monitoring()
    
    def get_watched_percent(self):
        if self.total_time == 0:
            return 0
        return (self.current_time / self.total_time) * 100
    
    def _save_progress(self):
        with self._save_lock:
            with self._state_lock:
                if not self.imdb_id or not self.content_type:
                    return
                
                if self.total_time == 0:
                    return
                
                imdb_id = self.imdb_id
                content_type = self.content_type
                current_time = self.current_time
                total_time = self.total_time
                season = self.season
                episode = self.episode
                title = self.title
                thumbnail = self.thumbnail
                fanart = self.fanart
                serie_name = self.serie_name
                original_name = self.original_name
                
            watched_percent = (current_time / total_time * 100) if total_time > 0 else 0
            
            try:
                if content_type == 'episode' and season is not None and episode is not None:
                    try:
                        db.save_episode_progress(
                            imdb_id=imdb_id,
                            season=season,
                            episode=episode,
                            current_time=current_time,
                            total_time=total_time,
                            title=title or '',
                            thumbnail=thumbnail or '',
                            fanart=fanart or '',
                            serie_name=serie_name or '',
                            original_name=original_name or ''
                        )
                        
                        if watched_percent >= 90:
                            self._sync_kodi_watched_status()
                        
                    except Exception:
                        xbmc.sleep(2000)
                        try:
                            db.save_episode_progress(
                                imdb_id=imdb_id,
                                season=season,
                                episode=episode,
                                current_time=current_time,
                                total_time=total_time,
                                title=title or '',
                                thumbnail=thumbnail or '',
                                fanart=fanart or '',
                                serie_name=serie_name or '',
                                original_name=original_name or ''
                            )
                        except:
                            pass
                        
            except Exception:
                pass
    
    def _sync_kodi_watched_status(self):
        try:
            with self._state_lock:
                if not self.imdb_id or not self.season or not self.episode:
                    return
                
                imdb_id = self.imdb_id
                season = self.season
                episode = self.episode
                
            query = {
                "jsonrpc": "2.0",
                "method": "VideoLibrary.GetEpisodes",
                "params": {
                    "filter": {
                        "and": [
                            {"field": "season", "operator": "is", "value": str(season)},
                            {"field": "episode", "operator": "is", "value": str(episode)}
                        ]
                    },
                    "properties": ["file", "uniqueid"]
                },
                "id": 1
            }
            
            result = json.loads(xbmc.executeJSONRPC(json.dumps(query)))
            
            if 'result' in result and 'episodes' in result['result']:
                for ep in result['result']['episodes']:
                    uniqueids = ep.get('uniqueid', {})
                    if uniqueids.get('imdb') == imdb_id or uniqueids.get('tmdb') == imdb_id:
                        episode_id = ep['episodeid']
                        
                        watched_query = {
                            "jsonrpc": "2.0",
                            "method": "VideoLibrary.SetEpisodeDetails",
                            "params": {
                                "episodeid": episode_id,
                                "playcount": 1,
                                "resume": {
                                    "position": 0,
                                    "total": 0
                                }
                            },
                            "id": 1
                        }
                        xbmc.executeJSONRPC(json.dumps(watched_query))
                        return
                    
        except Exception:
            pass
    
    def onPlayBackStopped(self):
        if self.upnext_service:
            self.upnext_service.stop_monitoring()
        
        with self._state_lock:
            self._stop_tracking = True
            was_tracking = self.is_tracking
            self.is_tracking = False
        
        if was_tracking:
            with self._state_lock:
                has_valid_state = (
                    self.content_type is not None and 
                    self.imdb_id is not None and 
                    self.current_time > 0
                )
            
            if has_valid_state:
                self._save_progress()
        
        with self._state_lock:
            self.imdb_id = None
            self.content_type = None
            self.season = None
            self.episode = None
            self._saved_at_90_percent = False
    
    def onPlayBackEnded(self):
        if self.upnext_service:
            self.upnext_service.stop_monitoring()
        
        with self._state_lock:
            self._stop_tracking = True
            was_tracking = self.is_tracking
            self.is_tracking = False
        
        if was_tracking:
            with self._state_lock:
                has_valid_state = (
                    self.content_type is not None and 
                    self.imdb_id is not None
                )
            
            if has_valid_state:
                with self._state_lock:
                    self.current_time = self.total_time
                
                self._save_progress()
        
        with self._state_lock:
            self.imdb_id = None
            self.content_type = None
            self.season = None
            self.episode = None
            self._saved_at_90_percent = False
    
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


def start_tracking_episode(imdb_id, season, episode, title, thumbnail='', fanart='', 
                          description='', serie_name='', original_name=''):
    player = get_player()
    
    player.start_playback(
        imdb_id=imdb_id,
        content_type='episode',
        title=title,
        season=season,
        episode=episode,
        thumbnail=thumbnail,
        fanart=fanart,
        description=description,
        serie_name=serie_name,
        original_name=original_name
    )
    
    return player
