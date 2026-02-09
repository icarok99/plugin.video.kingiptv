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
        
        with self._state_lock:
            if self.is_tracking:
                xbmc.log('KING IPTV - Parando tracking anterior antes de iniciar novo', xbmc.LOGINFO)
                self._stop_tracking = True
                self.is_tracking = False
                
                if self.upnext_service:
                    self.upnext_service.stop_monitoring()
        
        if self._tracking_thread and self._tracking_thread.is_alive():
            xbmc.log('KING IPTV - Aguardando thread anterior finalizar...', xbmc.LOGINFO)
            self._tracking_thread.join(timeout=2.0)
            if self._tracking_thread.is_alive():
                xbmc.log('KING IPTV - Thread anterior não finalizou no tempo limite', xbmc.LOGWARNING)
        
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
        
        xbmc.log('KING IPTV - Iniciando tracking loop (salvamento aos 90%)', xbmc.LOGINFO)
        
        waited = 0
        max_wait = 45
        
        while waited < max_wait:
            if monitor.waitForAbort(0.5):
                xbmc.log('KING IPTV - Abort detectado durante inicialização', xbmc.LOGINFO)
                self._cleanup_tracking_state()
                return
            
            if self._stop_tracking:
                xbmc.log('KING IPTV - Stop tracking solicitado durante inicialização', xbmc.LOGINFO)
                self._cleanup_tracking_state()
                return
            
            try:
                if self.isPlayingVideo() and self.getTotalTime() > 30:
                    break
            except:
                pass
            
            waited += 0.5
        
        if not self.isPlayingVideo():
            xbmc.log('KING IPTV - Vídeo não está tocando após espera', xbmc.LOGWARNING)
            self._cleanup_tracking_state()
            return
        
        try:
            total = self.getTotalTime()
            if total <= 30:
                xbmc.log('KING IPTV - Total time muito curto ({}s)'.format(total), xbmc.LOGWARNING)
                self._cleanup_tracking_state()
                return
            
            self.total_time = int(total)
            xbmc.log('KING IPTV - Reprodução confirmada. Total: {}s'.format(self.total_time), xbmc.LOGINFO)
            
        except Exception as e:
            xbmc.log('KING IPTV - Erro ao obter total_time: {}'.format(str(e)), xbmc.LOGERROR)
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
            xbmc.log('KING IPTV - Iniciando UpNext', xbmc.LOGINFO)
            try:
                self.upnext_service.start_monitoring(self.imdb_id, self.season, self.episode)
            except Exception as e:
                xbmc.log('KING IPTV - Erro ao iniciar Up Next: {}'.format(str(e)), xbmc.LOGERROR)
        
        self.current_time = 0
        
        while self.is_tracking and self.isPlayingVideo() and not self._stop_tracking:
            try:
                self.current_time = self.getTime()
                watched_percent = self.get_watched_percent()
                
                if watched_percent >= 90.0 and not self._saved_at_90_percent:
                    xbmc.log('KING IPTV - Atingiu 90%! Salvando progresso e marcando como assistido', xbmc.LOGINFO)
                    self._save_progress()
                    self._saved_at_90_percent = True
                
                if int(self.current_time) % 60 == 0:
                    xbmc.log('KING IPTV - Monitorando: {}s / {}s ({}%)'.format(
                        int(self.current_time), int(self.total_time), int(watched_percent)
                    ), xbmc.LOGDEBUG)
                
                if monitor.waitForAbort(2):
                    break
                    
            except Exception as e:
                xbmc.log('KING IPTV - Erro no tracking loop: {}'.format(str(e)), xbmc.LOGERROR)
                break
        
        if not self._saved_at_90_percent:
            xbmc.log('KING IPTV - Tracking finalizado antes de 90%, salvando progresso atual', xbmc.LOGINFO)
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
                    xbmc.log('KING IPTV - Estado inválido: sem imdb_id ou content_type', xbmc.LOGDEBUG)
                    return
                
                if self.total_time == 0:
                    xbmc.log('KING IPTV - Estado inválido: total_time é zero', xbmc.LOGWARNING)
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
            
            watched_percent = (current_time / total_time) * 100
            
            try:
                if content_type == 'episode':
                    if season is None or episode is None:
                        xbmc.log('KING IPTV - Episódio sem season/episode definidos', xbmc.LOGWARNING)
                        return
                    
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
                        xbmc.log('KING IPTV - Progresso do episódio salvo com sucesso', xbmc.LOGINFO)
                        
                        if watched_percent >= 90:
                            self._sync_kodi_watched_status()
                        
                    except Exception as e:
                        xbmc.log('KING IPTV - Erro ao salvar progresso do episódio: {}'.format(str(e)), xbmc.LOGERROR)
                        import traceback
                        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
                        
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
                            xbmc.log('KING IPTV - Retry de salvamento bem-sucedido', xbmc.LOGINFO)
                        except:
                            xbmc.log('KING IPTV - Retry de salvamento falhou', xbmc.LOGERROR)
                        
            except Exception as e:
                xbmc.log('KING IPTV - Erro geral ao salvar progresso: {}'.format(str(e)), xbmc.LOGERROR)
                import traceback
                xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
    
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
                        xbmc.log('KING IPTV - Episódio marcado como assistido no Kodi', xbmc.LOGINFO)
                        return
                    
        except Exception as e:
            xbmc.log('KING IPTV - Erro ao sincronizar com Kodi: {} (ignorando)'.format(str(e)), xbmc.LOGDEBUG)
    
    def onPlayBackStopped(self):
        xbmc.log('KING IPTV - onPlayBackStopped chamado', xbmc.LOGINFO)
        
        with self._state_lock:
            self._stop_tracking = True
            was_tracking = self.is_tracking
            self.is_tracking = False
        
        if self.upnext_service:
            self.upnext_service.stop_monitoring()
        
        if was_tracking:
            with self._state_lock:
                has_valid_state = (
                    self.content_type is not None and 
                    self.imdb_id is not None and 
                    self.current_time > 0
                )
            
            if has_valid_state:
                xbmc.log('KING IPTV - Salvando progresso final ao parar', xbmc.LOGINFO)
                self._save_progress()
        
        with self._state_lock:
            self.imdb_id = None
            self.content_type = None
            self.season = None
            self.episode = None
            self._saved_at_90_percent = False
        
        xbmc.log('KING IPTV - Player resetado', xbmc.LOGDEBUG)
    
    def onPlayBackEnded(self):
        xbmc.log('KING IPTV - onPlayBackEnded chamado', xbmc.LOGINFO)
        
        with self._state_lock:
            self._stop_tracking = True
            was_tracking = self.is_tracking
            self.is_tracking = False
        
        if self.upnext_service:
            self.upnext_service.stop_monitoring()
        
        if was_tracking:
            with self._state_lock:
                has_valid_state = (
                    self.content_type is not None and 
                    self.imdb_id is not None
                )
            
            if has_valid_state:
                with self._state_lock:
                    self.current_time = self.total_time
                
                xbmc.log('KING IPTV - Salvando progresso final ao terminar (100%)', xbmc.LOGINFO)
                self._save_progress()
        
        with self._state_lock:
            self.imdb_id = None
            self.content_type = None
            self.season = None
            self.episode = None
            self._saved_at_90_percent = False
        
        xbmc.log('KING IPTV - Player resetado', xbmc.LOGDEBUG)
    
    def onPlayBackError(self):
        xbmc.log('KING IPTV - onPlayBackError chamado', xbmc.LOGERROR)
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