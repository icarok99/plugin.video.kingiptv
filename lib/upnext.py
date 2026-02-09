# -*- coding: utf-8 -*-

import xbmc
import xbmcgui
import threading
import time
from datetime import datetime

class UpNextDialog(xbmcgui.WindowXMLDialog):
    
    BUTTON_PLAY_NOW = 3001
    BUTTON_CANCEL = 3002
    LABEL_NEXT_EPISODE = 3003
    IMAGE_THUMBNAIL = 3004
    PROGRESS_BAR = 3005
    
    def __init__(self, *args, **kwargs):
        self.next_episode_info = kwargs.get('next_episode_info', {})
        self.callback = kwargs.get('callback', None)
        self.countdown_seconds = kwargs.get('countdown_seconds', 10)
        self.auto_play = False
        self.cancelled = False
        self.countdown_thread = None
        self._stop_countdown = False
        
    def onInit(self):
        try:
            serie_name = self.next_episode_info.get('serie_name', '')
            next_season = self.next_episode_info.get('next_season', 0)
            next_episode = self.next_episode_info.get('next_episode', 0)
            episode_title = self.next_episode_info.get('episode_title', '')
            thumbnail = self.next_episode_info.get('thumbnail', '')
            
            next_text = '{}x{:02d}'.format(next_season, next_episode)
            if episode_title:
                next_text += ' - {}'.format(episode_title)
            
            self.getControl(self.LABEL_NEXT_EPISODE).setLabel(next_text)
            
            if thumbnail:
                self.getControl(self.IMAGE_THUMBNAIL).setImage(thumbnail)
            
            try:
                self.setFocusId(self.BUTTON_PLAY_NOW)
            except:
                pass
            
            self._start_countdown()
            
        except Exception as e:
            xbmc.log('KING IPTV UpNext - Erro no onInit: {}'.format(str(e)), xbmc.LOGERROR)
    
    def _start_countdown(self):
        self._stop_countdown = False
        self.countdown_thread = threading.Thread(target=self._countdown_loop)
        self.countdown_thread.daemon = True
        self.countdown_thread.start()
    
    def _countdown_loop(self):
        remaining = self.countdown_seconds
        
        while remaining > 0 and not self._stop_countdown:
            try:
                progress = int(((self.countdown_seconds - remaining) / float(self.countdown_seconds)) * 100)
                self.getControl(self.PROGRESS_BAR).setPercent(progress)
                
                self.getControl(self.BUTTON_PLAY_NOW).setLabel('Reproduzir ({}s)'.format(remaining))
                
                time.sleep(1)
                remaining -= 1
                
            except Exception as e:
                xbmc.log('KING IPTV UpNext - Erro no countdown: {}'.format(str(e)), xbmc.LOGERROR)
                break
        
        if not self._stop_countdown and remaining == 0:
            self.auto_play = True
            self.close()
    
    def onClick(self, controlId):
        if controlId == self.BUTTON_PLAY_NOW:
            xbmc.log('KING IPTV UpNext - Botão Reproduzir clicado', xbmc.LOGINFO)
            self.auto_play = True
            self._stop_countdown = True
            self.close()
            
        elif controlId == self.BUTTON_CANCEL:
            xbmc.log('KING IPTV UpNext - Botão Cancelar clicado', xbmc.LOGINFO)
            self.cancelled = True
            self._stop_countdown = True
            self.close()
    
    def onAction(self, action):
        action_id = action.getId()
        
        xbmc.log('KING IPTV UpNext - Ação recebida: {}'.format(action_id), xbmc.LOGDEBUG)
        
        if action_id in (xbmcgui.ACTION_SELECT_ITEM, xbmcgui.ACTION_PLAYER_PLAY):
            try:
                focused_control = self.getFocusId()
                xbmc.log('KING IPTV UpNext - SELECT pressionado no controle ID: {}'.format(focused_control), xbmc.LOGINFO)
                
                if focused_control == self.BUTTON_PLAY_NOW:
                    xbmc.log('KING IPTV UpNext - Reproduzir selecionado via controle', xbmc.LOGINFO)
                    self.auto_play = True
                    self._stop_countdown = True
                    self.close()
                    return
                    
                elif focused_control == self.BUTTON_CANCEL:
                    xbmc.log('KING IPTV UpNext - Cancelar selecionado via controle', xbmc.LOGINFO)
                    self.cancelled = True
                    self._stop_countdown = True
                    self.close()
                    return
            except Exception as e:
                xbmc.log('KING IPTV UpNext - Erro ao processar SELECT: {}'.format(str(e)), xbmc.LOGERROR)
        
        elif action_id in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_STOP):
            xbmc.log('KING IPTV UpNext - VOLTAR pressionado via controle', xbmc.LOGINFO)
            self.cancelled = True
            self._stop_countdown = True
            self.close()
            return
        
        elif action_id in (xbmcgui.ACTION_MOVE_LEFT, xbmcgui.ACTION_MOVE_RIGHT, 
                          xbmcgui.ACTION_MOVE_UP, xbmcgui.ACTION_MOVE_DOWN):
            pass
        
        elif action_id == xbmcgui.ACTION_PLAYER_PLAY:
            xbmc.log('KING IPTV UpNext - PLAY direto pressionado', xbmc.LOGINFO)
            self.auto_play = True
            self._stop_countdown = True
            self.close()
            return


class UpNextService:
    
    def __init__(self, player, database):
        self.player = player
        self.db = database
        
        import xbmcaddon
        addon = xbmcaddon.Addon()
        
        self.enabled = addon.getSettingBool('upnext_enabled') if hasattr(addon, 'getSettingBool') else True
        self.countdown_seconds = addon.getSettingInt('upnext_countdown_seconds') if hasattr(addon, 'getSettingInt') else 10
        self.trigger_seconds = addon.getSettingInt('upnext_trigger_seconds') if hasattr(addon, 'getSettingInt') else 30
        
        if self.countdown_seconds == 0:
            self.countdown_seconds = 10
        if self.trigger_seconds == 0:
            self.trigger_seconds = 30
            
        self.monitoring = False
        self.monitor_thread = None
        self._stop_monitoring = False
        self._monitor_lock = threading.Lock()
        
        xbmc.log('KING IPTV UpNext - Inicializado com: enabled={}, countdown={}s, trigger={}s'.format(
            self.enabled, self.countdown_seconds, self.trigger_seconds
        ), xbmc.LOGINFO)
        
    def start_monitoring(self, imdb_id, season, episode):
        if not self.enabled:
            xbmc.log('KING IPTV UpNext - Serviço desabilitado', xbmc.LOGDEBUG)
            return
        
        with self._monitor_lock:
            if self.monitoring:
                xbmc.log('KING IPTV UpNext - Parando monitoramento anterior', xbmc.LOGINFO)
                self._stop_monitoring = True
                self.monitoring = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            xbmc.log('KING IPTV UpNext - Aguardando thread anterior...', xbmc.LOGDEBUG)
            self.monitor_thread.join(timeout=2.0)
        
        next_metadata = self._find_next_episode(imdb_id, season, episode)
        
        if not next_metadata:
            xbmc.log('KING IPTV UpNext - Não há próximo episódio após S{}E{}'.format(
                season, episode
            ), xbmc.LOGDEBUG)
            return
        
        watching = self.db.get_episode_watching(imdb_id)
        serie_name = watching.get('serie_name', '') if watching else ''
        original_name = watching.get('original_name', '') if watching else ''
        
        next_info = {
            'imdb_id': imdb_id,
            'serie_name': serie_name or next_metadata.get('serie_name', ''),
            'original_name': original_name or next_metadata.get('original_name', ''),
            'next_season': next_metadata.get('season'),
            'next_episode': next_metadata.get('episode'),
            'episode_title': next_metadata.get('episode_title', ''),
            'thumbnail': next_metadata.get('thumbnail', ''),
            'fanart': next_metadata.get('fanart', ''),
            'description': next_metadata.get('description', '')
        }
        
        xbmc.log('KING IPTV UpNext - Iniciando monitoramento para próximo: S{}E{}'.format(
            next_info['next_season'], next_info['next_episode']
        ), xbmc.LOGINFO)
        
        with self._monitor_lock:
            self._stop_monitoring = False
            self.monitoring = True
        
        self.monitor_thread = threading.Thread(
            target=self._monitor_playback,
            args=(next_info,)
        )
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def _find_next_episode(self, imdb_id, current_season, current_episode):
        try:
            next_in_season = self.db.get_episode_metadata(imdb_id, current_season, current_episode + 1)
            if next_in_season:
                xbmc.log('KING IPTV UpNext - Próximo episódio encontrado: S{}E{}'.format(
                    current_season, current_episode + 1
                ), xbmc.LOGINFO)
                return next_in_season
            
            next_season_ep = self.db.get_episode_metadata(imdb_id, current_season + 1, 1)
            if next_season_ep:
                xbmc.log('KING IPTV UpNext - Próximo episódio encontrado: S{}E1'.format(
                    current_season + 1
                ), xbmc.LOGINFO)
                return next_season_ep
            
            from lib.database import KingDatabase
            with self.db._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM episodes_metadata
                    WHERE imdb_id = ?
                        AND (season > ? OR (season = ? AND episode > ?))
                    ORDER BY season ASC, episode ASC
                    LIMIT 1
                ''', (imdb_id, current_season, current_season, current_episode))
                
                row = cursor.fetchone()
                if row:
                    result = dict(row)
                    xbmc.log('KING IPTV UpNext - Próximo episódio encontrado via query direta: S{}E{}'.format(
                        result['season'], result['episode']
                    ), xbmc.LOGINFO)
                    return result
            
            return None
            
        except Exception as e:
            xbmc.log('KING IPTV UpNext - Erro ao buscar próximo episódio: {}'.format(str(e)), xbmc.LOGERROR)
            import traceback
            xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
            return None
    
    def _monitor_playback(self, next_info):
        monitor = xbmc.Monitor()
        upnext_shown = False
        
        xbmc.log('KING IPTV UpNext - Thread de monitoramento iniciada', xbmc.LOGINFO)
        
        for _ in range(60):
            if self.player.isPlayingVideo():
                break
            if monitor.waitForAbort(0.5) or self._stop_monitoring:
                with self._monitor_lock:
                    self.monitoring = False
                return
        
        if not self.player.isPlayingVideo():
            xbmc.log('KING IPTV UpNext - Ainda não está tocando após longa espera', xbmc.LOGWARNING)
            with self._monitor_lock:
                self.monitoring = False
            return
        
        total_time = 0
        for _ in range(30):
            try:
                total_time = self.player.getTotalTime()
                if total_time > 60:
                    break
            except:
                pass
            
            if self._stop_monitoring:
                with self._monitor_lock:
                    self.monitoring = False
                return
            
            monitor.waitForAbort(0.5)
        
        if total_time <= 60:
            xbmc.log('KING IPTV UpNext - total_time inválido ({}) → abortando'.format(int(total_time)), xbmc.LOGWARNING)
            with self._monitor_lock:
                self.monitoring = False
            return
        
        safety_margin = 30
        start_at_90_percent = total_time * 0.9
        start_at_trigger = total_time - self.trigger_seconds - safety_margin
        start_monitoring_at = min(start_at_90_percent, start_at_trigger)
        
        light_check_interval = min(60, max(10, int(self.trigger_seconds / 2)))
        
        xbmc.log('KING IPTV UpNext - Total: {}s, trigger: {}s, monitoramento ativo a partir de: {}s ({}%)'.format(
            int(total_time), 
            self.trigger_seconds, 
            int(start_monitoring_at),
            int((start_monitoring_at / total_time) * 100)
        ), xbmc.LOGINFO)
        
        while self.player.isPlayingVideo() and not self._stop_monitoring:
            try:
                current_time = self.player.getTime()
                
                if current_time >= start_monitoring_at:
                    xbmc.log('KING IPTV UpNext - Entrando em monitoramento ativo', xbmc.LOGDEBUG)
                    break
                
                if monitor.waitForAbort(light_check_interval):
                    break
                    
            except Exception as e:
                xbmc.log('KING IPTV UpNext - Erro na fase leve: {}'.format(str(e)), xbmc.LOGERROR)
                break
        
        while self.player.isPlayingVideo() and not self._stop_monitoring:
            try:
                current_time = self.player.getTime()
                remaining_time = total_time - current_time
                
                if remaining_time <= self.trigger_seconds and not upnext_shown:
                    xbmc.log('KING IPTV UpNext - Exibindo dialog (faltam {}s)'.format(
                        int(remaining_time)
                    ), xbmc.LOGINFO)
                    
                    upnext_shown = True
                    should_play_next = self._show_upnext_dialog(next_info)
                    
                    self.player.stop()
                    
                    if should_play_next:
                        xbmc.log('KING IPTV UpNext - Usuário optou por reproduzir próximo episódio', xbmc.LOGINFO)
                        xbmc.sleep(500)
                        self._play_next_episode(next_info)
                    else:
                        xbmc.log('KING IPTV UpNext - Usuário cancelou reprodução', xbmc.LOGINFO)
                    
                    break
                
                if monitor.waitForAbort(2):
                    break
                    
            except Exception as e:
                xbmc.log('KING IPTV UpNext - Erro no monitoramento ativo: {}'.format(str(e)), xbmc.LOGERROR)
                break
        
        with self._monitor_lock:
            self.monitoring = False
        
        xbmc.log('KING IPTV UpNext - Monitoramento finalizado', xbmc.LOGINFO)
    
    def _show_upnext_dialog(self, next_info):
        try:
            import xbmcaddon
            addon = xbmcaddon.Addon()
            
            xbmc.log('KING IPTV UpNext - Criando dialog customizado para controle remoto', xbmc.LOGINFO)
            
            dialog = UpNextDialog(
                'upnext-dialog.xml',
                addon.getAddonInfo('path'),
                'default',
                '1080i',
                next_episode_info=next_info,
                countdown_seconds=self.countdown_seconds
            )
            dialog.doModal()
            
            result = dialog.auto_play and not dialog.cancelled
            
            xbmc.log('KING IPTV UpNext - Dialog fechado: auto_play={}, cancelled={}, result={}'.format(
                dialog.auto_play, dialog.cancelled, result
            ), xbmc.LOGINFO)
            
            del dialog
            return result
                
        except Exception as e:
            xbmc.log('KING IPTV UpNext - Erro ao exibir dialog: {}'.format(str(e)), xbmc.LOGERROR)
            import traceback
            xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
            return False
    
    def _play_next_episode(self, next_info):
        try:
            try:
                from urllib import urlencode
            except ImportError:
                from urllib.parse import urlencode
            
            params = {
                'serie_name': next_info.get('serie_name', ''),
                'original_name': next_info.get('original_name', ''),
                'season_num': str(next_info.get('next_season', 1)),
                'episode_num': str(next_info.get('next_episode', 1)),
                'episode_title': next_info.get('episode_title', ''),
                'iconimage': next_info.get('thumbnail', ''),
                'fanart': next_info.get('fanart', ''),
                'imdbnumber': next_info.get('imdb_id', ''),
                'description': next_info.get('description', ''),
                'from_upnext': 'true'
            }
            
            plugin_url = 'plugin://plugin.video.kingiptv/play_resolve_series/{}'.format(urlencode(params))
            
            xbmc.log('KING IPTV UpNext - Reproduzindo URL: {}'.format(plugin_url), xbmc.LOGINFO)
            
            xbmc.executebuiltin('PlayMedia({})'.format(plugin_url))
            
        except Exception as e:
            xbmc.log('KING IPTV UpNext - Erro ao reproduzir próximo episódio: {}'.format(str(e)), xbmc.LOGERROR)
            import traceback
            xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
    
    def stop_monitoring(self):
        with self._monitor_lock:
            self._stop_monitoring = True
            self.monitoring = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=3.0)
            if self.monitor_thread.is_alive():
                xbmc.log('KING IPTV UpNext - Thread não finalizou no tempo limite', xbmc.LOGWARNING)
        
        xbmc.log('KING IPTV UpNext - Monitoramento parado', xbmc.LOGDEBUG)
    
    def is_monitoring(self):
        with self._monitor_lock:
            return self.monitoring


_upnext_service = None
_upnext_lock = threading.Lock()


def get_upnext_service(player, database):
    global _upnext_service
    
    with _upnext_lock:
        if _upnext_service is None:
            _upnext_service = UpNextService(player, database)
        return _upnext_service