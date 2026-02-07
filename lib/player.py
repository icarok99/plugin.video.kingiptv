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
        
        self.resume_point = 0
        
        self._monitor = None
        self._tracking_thread = None
        self._stop_tracking = False
        
        self.upnext_service = get_upnext_service(self, db)
    
    def start_playback(self, imdb_id, content_type, title, season=None, episode=None,
                      thumbnail='', fanart='', description='', resume_point=0,
                      serie_name='', original_name=''):
        if self.is_tracking:
            xbmc.log('KING IPTV - Parando tracking anterior antes de iniciar novo', xbmc.LOGINFO)
            self._stop_tracking = True
            self.is_tracking = False
            if self.upnext_service:
                self.upnext_service.stop_monitoring()
            import time
            time.sleep(0.5)
        
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
        self.resume_point = resume_point
        self.is_tracking = True
        self._stop_tracking = False
        
        self._tracking_thread = threading.Thread(target=self._tracking_loop)
        self._tracking_thread.daemon = True
        self._tracking_thread.start()
    
    def _tracking_loop(self):
        monitor = xbmc.Monitor()
        last_save_time = 0
        save_interval = 10
        
        xbmc.log('KING IPTV - Iniciando tracking loop', xbmc.LOGINFO)
        
        waited = 0
        max_wait = 45
        
        while waited < max_wait:
            if monitor.waitForAbort(0.5):
                return
            if self.isPlayingVideo() and self.getTotalTime() > 30:
                break
            waited += 0.5
        
        if not self.isPlayingVideo() or self.getTotalTime() <= 30:
            xbmc.log('KING IPTV - Playback não iniciado corretamente após espera → cancelando tracking e UpNext', xbmc.LOGWARNING)
            self.is_tracking = False
            return
        
        try:
            self.total_time = int(self.getTotalTime())
            xbmc.log('KING IPTV - Reprodução confirmada. Total: {}s'.format(self.total_time), xbmc.LOGINFO)
        except:
            xbmc.log('KING IPTV - Ainda sem total_time após espera longa', xbmc.LOGERROR)
            return
        
        if self.content_type == 'episode' and self.season and self.episode and self.imdb_id:
            xbmc.log('KING IPTV - Iniciando UpNext AGORA que vídeo está tocando', xbmc.LOGINFO)
            try:
                self.upnext_service.start_monitoring(self.imdb_id, self.season, self.episode)
            except Exception as e:
                xbmc.log('KING IPTV - Erro ao iniciar Up Next: {}'.format(str(e)), xbmc.LOGERROR)
        
        self.current_time = 0
        self._save_progress()
        
        while self.is_tracking and self.isPlayingVideo() and not self._stop_tracking:
            try:
                self.current_time = self.getTime()
                watched_percent = self.get_watched_percent()
                
                if self.current_time - last_save_time >= save_interval:
                    xbmc.log('KING IPTV - Salvando progresso: {}s / {}s ({}%)'.format(
                        int(self.current_time), int(self.total_time), int(watched_percent)
                    ), xbmc.LOGINFO)
                    self._save_progress()
                    last_save_time = self.current_time
                
                if monitor.waitForAbort(1):
                    break
                    
            except Exception as e:
                xbmc.log('KING IPTV - Erro no tracking loop: {}'.format(str(e)), xbmc.LOGERROR)
                break
        
        xbmc.log('KING IPTV - Tracking loop finalizado, salvando progresso final', xbmc.LOGINFO)
        self._save_progress()
    
    def get_watched_percent(self):
        if self.total_time == 0:
            return 0
        return (self.current_time / self.total_time) * 100
    
    def _save_progress(self):
        if not self.imdb_id or not self.content_type:
            xbmc.log('KING IPTV - Sem imdb_id ou content_type, pulando salvamento', xbmc.LOGDEBUG)
            return
        
        try:
            watched_percent = self.get_watched_percent()
            
            xbmc.log('KING IPTV - Tentando salvar progresso: {}% ({}s / {}s)'.format(
                int(watched_percent), int(self.current_time), int(self.total_time)
            ), xbmc.LOGINFO)
            
            if self.content_type == 'episode':
                if not self.season or not self.episode:
                    xbmc.log('KING IPTV - Sem season ou episode, pulando salvamento', xbmc.LOGWARNING)
                    return
                
                try:
                    xbmc.log('KING IPTV - Chamando db.save_episode_progress...', xbmc.LOGINFO)
                    db.save_episode_progress(
                        imdb_id=self.imdb_id,
                        season=self.season,
                        episode=self.episode,
                        current_time=self.current_time,
                        total_time=self.total_time,
                        title=self.title or '',
                        thumbnail=self.thumbnail or '',
                        fanart=self.fanart or '',
                        serie_name=self.serie_name or '',
                        original_name=self.original_name or ''
                    )
                    xbmc.log('KING IPTV - Progresso do episódio salvo com sucesso', xbmc.LOGINFO)
                    
                    if watched_percent >= 90:
                        self._sync_kodi_watched_status()
                    
                except Exception as e:
                    xbmc.log('KING IPTV - Erro ao salvar progresso do episódio: {}'.format(str(e)), xbmc.LOGERROR)
                    import traceback
                    xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
                    raise
                    
        except Exception as e:
            xbmc.log('KING IPTV - Erro geral ao salvar progresso: {}'.format(str(e)), xbmc.LOGERROR)
            import traceback
            xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
    
    def _sync_kodi_watched_status(self):
        try:
            if not self.imdb_id or not self.season or not self.episode:
                return
                
            query = {
                "jsonrpc": "2.0",
                "method": "VideoLibrary.GetEpisodes",
                "params": {
                    "filter": {
                        "and": [
                            {"field": "season", "operator": "is", "value": str(self.season)},
                            {"field": "episode", "operator": "is", "value": str(self.episode)}
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
                    if uniqueids.get('imdb') == self.imdb_id or uniqueids.get('tmdb') == self.imdb_id:
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
                        xbmc.log('KING IPTV - Episódio marcado como assistido no Kodi', xbmc.LOGINFO)
                    
                    return
                    
        except Exception as e:
            xbmc.log('KING IPTV - Erro ao sincronizar com Kodi: {} (ignorando)'.format(str(e)), xbmc.LOGDEBUG)
    
    def onPlayBackStopped(self):
        xbmc.log('KING IPTV - onPlayBackStopped chamado', xbmc.LOGINFO)
        self._stop_tracking = True
        self.is_tracking = False
        
        if self.upnext_service:
            self.upnext_service.stop_monitoring()
        
        if self.content_type and self.imdb_id and self.current_time > 0:
            xbmc.log('KING IPTV - Salvando progresso final ao parar', xbmc.LOGINFO)
            self._save_progress()
        
        self.imdb_id = None
        self.content_type = None
        self.season = None
        self.episode = None
        
        xbmc.log('KING IPTV - Player resetado', xbmc.LOGDEBUG)
    
    def onPlayBackEnded(self):
        xbmc.log('KING IPTV - onPlayBackEnded chamado', xbmc.LOGINFO)
        self._stop_tracking = True
        self.is_tracking = False
        
        if self.upnext_service:
            self.upnext_service.stop_monitoring()
        
        if self.content_type and self.imdb_id:
            self.current_time = self.total_time
            xbmc.log('KING IPTV - Salvando progresso final ao terminar (100%)', xbmc.LOGINFO)
            self._save_progress()
        
        self.imdb_id = None
        self.content_type = None
        self.season = None
        self.episode = None
        
        xbmc.log('KING IPTV - Player resetado', xbmc.LOGDEBUG)
    
    def onPlayBackError(self):
        self._stop_tracking = True
        self.is_tracking = False


class Monitor(xbmc.Monitor):
    
    def __init__(self):
        super(Monitor, self).__init__()
        self.playbackerror = False
    
    def onNotification(self, sender, method, data):
        if method == 'Player.OnStop':
            self.playbackerror = True


_global_player = None


def get_player():
    global _global_player
    if _global_player is None:
        _global_player = KingPlayer()
    return _global_player


def start_tracking_episode(imdb_id, season, episode, title, thumbnail='', fanart='', 
                          description='', serie_name='', original_name=''):
    progress = db.get_episode_progress(imdb_id, season, episode)
    resume_point = progress['current_time'] if progress else 0
    
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
        resume_point=resume_point,
        serie_name=serie_name,
        original_name=original_name
    )
    
    return player