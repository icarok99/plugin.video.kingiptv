# -*- coding: utf-8 -*-

import xbmc
import xbmcgui
import threading
import time

import xbmcaddon as _xbmcaddon
_addon = _xbmcaddon.Addon()

def getString(string_id):
    return _addon.getLocalizedString(string_id)


class UpNextDialog(xbmcgui.WindowXMLDialog):
    
    BUTTON_PLAY_NOW = 3001
    BUTTON_CANCEL = 3002
    LABEL_NEXT_EPISODE = 3003
    IMAGE_THUMBNAIL = 3004
    PROGRESS_BAR = 3005
    
    def __init__(self, *args, **kwargs):
        self.next_episode_info = kwargs.get('next_episode_info', {})
        self.countdown_seconds = kwargs.get('countdown_seconds', 10)
        self.auto_play = False
        self.cancelled = False
        self.countdown_thread = None
        self._stop_countdown = False
        self.player = xbmc.Player()
        
    def onInit(self):
        try:
            serie_name = self.next_episode_info.get('serie_name', '')
            next_season = self.next_episode_info.get('next_season', 0)
            next_episode = self.next_episode_info.get('next_episode', 0)
            episode_title = self.next_episode_info.get('episode_title', '')
            thumbnail = self.next_episode_info.get('thumbnail', '')
            
            if episode_title:
                next_text = '{}x{:02d} - {}'.format(next_season, next_episode, episode_title)
            else:
                next_text = '{}x{:02d}'.format(next_season, next_episode)
            
            self.getControl(self.LABEL_NEXT_EPISODE).setLabel(next_text)
            
            if thumbnail:
                self.getControl(self.IMAGE_THUMBNAIL).setImage(thumbnail)
            
            try:
                self.setFocusId(self.BUTTON_PLAY_NOW)
            except:
                pass
            
            self._start_countdown()
            
        except Exception:
            pass
    
    def _start_countdown(self):
        self._stop_countdown = False
        self.countdown_thread = threading.Thread(target=self._countdown_loop)
        self.countdown_thread.daemon = True
        self.countdown_thread.start()
    
    def _countdown_loop(self):
        remaining = self.countdown_seconds
        
        while remaining > 0 and not self._stop_countdown:
            try:
                progress = int((remaining / float(self.countdown_seconds)) * 100)
                self.getControl(self.PROGRESS_BAR).setPercent(progress)
                
                self.getControl(self.BUTTON_PLAY_NOW).setLabel(getString(32108).format(remaining))
                
                time.sleep(1)
                remaining -= 1
                
            except Exception:
                break
        
        if not self._stop_countdown and remaining == 0:
            self.auto_play = True
            self.close()
    
    def onClick(self, controlId):
        if controlId == self.BUTTON_PLAY_NOW:
            try:
                total_time = self.player.getTotalTime()
                self.player.seekTime(total_time - 3)
            except:
                pass
            self.auto_play = True
            self._stop_countdown = True
            self.close()
            
        elif controlId == self.BUTTON_CANCEL:
            self.cancelled = True
            self._stop_countdown = True
            self.close()
    
    def onAction(self, action):
        action_id = action.getId()
        
        if action_id in (xbmcgui.ACTION_SELECT_ITEM, xbmcgui.ACTION_PLAYER_PLAY):
            try:
                focused_control = self.getFocusId()
                
                if focused_control == self.BUTTON_PLAY_NOW:
                    try:
                        total_time = self.player.getTotalTime()
                        self.player.seekTime(total_time - 3)
                    except:
                        pass
                    self.auto_play = True
                    self._stop_countdown = True
                    self.close()
                    return
                    
                elif focused_control == self.BUTTON_CANCEL:
                    self.cancelled = True
                    self._stop_countdown = True
                    self.close()
                    return
            except Exception:
                pass
        
        elif action_id in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_STOP):
            self.cancelled = True
            self._stop_countdown = True
            self.close()
            return
        
        elif action_id in (xbmcgui.ACTION_MOVE_LEFT, xbmcgui.ACTION_MOVE_RIGHT, 
                          xbmcgui.ACTION_MOVE_UP, xbmcgui.ACTION_MOVE_DOWN):
            pass
        
        elif action_id == xbmcgui.ACTION_PLAYER_PLAY:
            try:
                total_time = self.player.getTotalTime()
                self.player.seekTime(total_time - 3)
            except:
                pass
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
        
        self._dialog_shown = False
        self._dialog_lock = threading.Lock()
    
    def _parse_episode_format(self, text):
        """Extrai season e episode do formato '1x2 Nome do Episódio'"""
        import re
        if not text:
            return None, None, None
        
        match = re.match(r'^(\d+)x(\d+)\s*(.*)', text)
        if match:
            season = int(match.group(1))
            episode = int(match.group(2))
            title = match.group(3).strip()
            return season, episode, title
        return None, None, None
        
    def start_monitoring(self, imdb_id, season, episode):
        if not self.enabled:
            return
        
        with self._dialog_lock:
            self._dialog_shown = False
        
        with self._monitor_lock:
            if self.monitoring:
                self._stop_monitoring = True
                self.monitoring = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=3.0)
        
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        
        if playlist.size() == 0 or playlist.getposition() >= (playlist.size() - 1):
            return
        
        next_info = self._get_next_from_playlist()
        
        if not next_info or not next_info.get('next_season'):
            next_episode_metadata = self.db.get_next_episode_metadata(imdb_id, season, episode)
            if not next_episode_metadata:
                return
                
            next_info = {
                'imdb_id': imdb_id,
                'serie_name': next_episode_metadata.get('serie_name', ''),
                'original_name': next_episode_metadata.get('original_name', ''),
                'next_season': next_episode_metadata.get('season'),
                'next_episode': next_episode_metadata.get('episode'),
                'episode_title': next_episode_metadata.get('episode_title', ''),
                'thumbnail': next_episode_metadata.get('thumbnail', ''),
                'fanart': next_episode_metadata.get('fanart', ''),
                'description': next_episode_metadata.get('description', '')
            }
        
        with self._monitor_lock:
            self.monitoring = True
            self._stop_monitoring = False
        
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            args=(next_info,)
        )
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def _get_next_from_playlist(self):
        try:
            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            current_position = playlist.getposition()
            
            if current_position >= (playlist.size() - 1):
                return None
            
            next_item = playlist[current_position + 1]
            
            if hasattr(next_item, 'getVideoInfoTag'):
                info_tag = next_item.getVideoInfoTag()
                
                title = info_tag.getTitle() if hasattr(info_tag, 'getTitle') else ''
                season, episode, episode_title = self._parse_episode_format(title)
                
                return {
                    'serie_name': info_tag.getTVShowTitle() if hasattr(info_tag, 'getTVShowTitle') else '',
                    'original_name': info_tag.getOriginalTitle() if hasattr(info_tag, 'getOriginalTitle') else '',
                    'next_season': season if season else 0,
                    'next_episode': episode if episode else 0,
                    'episode_title': episode_title,
                    'thumbnail': next_item.getArt('thumb'),
                    'fanart': next_item.getArt('fanart'),
                    'description': info_tag.getPlot() if hasattr(info_tag, 'getPlot') else ''
                }
            else:
                label = next_item.getLabel()
                season, episode, episode_title = self._parse_episode_format(label)
                
                return {
                    'serie_name': '',
                    'next_season': season if season else 0,
                    'next_episode': episode if episode else 0,
                    'episode_title': episode_title if episode_title else label,
                    'thumbnail': next_item.getArt('thumb'),
                    'fanart': next_item.getArt('fanart'),
                    'description': ''
                }
                
        except Exception:
            return None
    
    def _monitoring_loop(self, next_info):
        monitor = xbmc.Monitor()
        
        waited = 0
        max_wait_time = 30
        
        while waited < max_wait_time:
            if not self.player.isPlayingVideo():
                if monitor.waitForAbort(0.5):
                    with self._monitor_lock:
                        self.monitoring = False
                    return
                waited += 0.5
                continue
            else:
                break
        
        if not self.player.isPlayingVideo():
            with self._monitor_lock:
                self.monitoring = False
            return
        
        total_time = 0
        time_attempts = 0
        max_attempts = 60
        
        while time_attempts < max_attempts:
            try:
                total_time = self.player.getTotalTime()
                if total_time > 60:
                    break
            except:
                pass
            
            time_attempts += 1
            
            if self._stop_monitoring:
                with self._monitor_lock:
                    self.monitoring = False
                return
            
            monitor.waitForAbort(0.5)
        
        if total_time <= 60:
            with self._monitor_lock:
                self.monitoring = False
            return
        
        safety_margin = 30
        start_at_90_percent = total_time * 0.9
        start_at_trigger = total_time - self.trigger_seconds - safety_margin
        start_monitoring_at = min(start_at_90_percent, start_at_trigger)
        
        light_check_interval = min(60, max(10, int(self.trigger_seconds / 2)))
        
        while self.player.isPlayingVideo() and not self._stop_monitoring:
            try:
                current_time = self.player.getTime()
                
                if current_time >= start_monitoring_at:
                    break
                
                if monitor.waitForAbort(light_check_interval):
                    break
                    
            except Exception:
                break
        
        while self.player.isPlayingVideo() and not self._stop_monitoring:
            try:
                current_time = self.player.getTime()
                remaining_time = total_time - current_time
                
                with self._dialog_lock:
                    dialog_already_shown = self._dialog_shown
                
                if remaining_time <= self.trigger_seconds and not dialog_already_shown:
                    with self._dialog_lock:
                        if not self._dialog_shown:
                            self._dialog_shown = True
                            
                            self._show_upnext_dialog(next_info)
                            break
                        else:
                            break
                
                if monitor.waitForAbort(2):
                    break
                    
            except Exception:
                break
        
        with self._monitor_lock:
            self.monitoring = False
    
    def _show_upnext_dialog(self, next_info):
        try:
            import xbmcaddon
            addon = xbmcaddon.Addon()
            
            dialog = UpNextDialog(
                'upnext-dialog.xml',
                addon.getAddonInfo('path'),
                'default',
                '1080i',
                next_episode_info=next_info,
                countdown_seconds=self.countdown_seconds
            )
            dialog.doModal()
            
            del dialog
                
        except Exception:
            pass
    
    def stop_monitoring(self):
        with self._monitor_lock:
            self._stop_monitoring = True
            was_monitoring = self.monitoring
            self.monitoring = False
        
        if was_monitoring and self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=3.0)
        
        with self._dialog_lock:
            self._dialog_shown = False
    
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