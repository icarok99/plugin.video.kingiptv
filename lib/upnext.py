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

    def _do_advance(self):
        try:
            total_time = self.player.getTotalTime()
            self.player.seekTime(total_time - 1)
        except Exception:
            pass

    def onInit(self):
        try:
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
            except Exception:
                pass
            self._start_countdown()
        except Exception:
            pass

    def _start_countdown(self):
        self._stop_countdown = False
        self.countdown_thread = threading.Thread(target=self._countdown_loop, daemon=True)
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
            self._do_advance()
            self.close()

    def onClick(self, controlId):
        if controlId == self.BUTTON_PLAY_NOW:
            self.auto_play = True
            self._stop_countdown = True
            self._do_advance()
            self.close()
        elif controlId == self.BUTTON_CANCEL:
            self.cancelled = True
            self._stop_countdown = True
            self.close()

    def onAction(self, action):
        action_id = action.getId()
        if action_id in (xbmcgui.ACTION_SELECT_ITEM, xbmcgui.ACTION_PLAYER_PLAY):
            try:
                focused = self.getFocusId()
                if focused == self.BUTTON_PLAY_NOW:
                    self.auto_play = True
                    self._stop_countdown = True
                    self._do_advance()
                    self.close()
                    return
                elif focused == self.BUTTON_CANCEL:
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
        elif action_id in (xbmcgui.ACTION_MOVE_LEFT, xbmcgui.ACTION_MOVE_RIGHT, xbmcgui.ACTION_MOVE_UP, xbmcgui.ACTION_MOVE_DOWN):
            pass
        elif action_id == xbmcgui.ACTION_PLAYER_PLAY:
            self.auto_play = True
            self._stop_countdown = True
            self._do_advance()
            self.close()

class UpNextService:

    def __init__(self, database):
        self.db = database
        import xbmcaddon
        addon = xbmcaddon.Addon()
        self.enabled = self._get_bool(addon, 'upnext_enabled', True)
        self.countdown_seconds = self._get_int(addon, 'upnext_countdown_seconds', 10)
        self.trigger_seconds = self._get_int(addon, 'upnext_trigger_seconds', 30)
        self._watched_marked = False

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
            return None
        self._watched_marked = False
        next_info = None
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        if playlist.size() > 0 and playlist.getposition() < (playlist.size() - 1):
            next_info = self._get_next_from_playlist()
        if not next_info or not next_info.get('next_season'):
            meta = self.db.get_next_episode_metadata(imdb_id, season, episode)
            if meta:
                next_info = {
                    'imdb_id': imdb_id,
                    'serie_name': meta.get('serie_name', ''),
                    'original_name': meta.get('original_name', ''),
                    'next_season': meta.get('season'),
                    'next_episode': meta.get('episode'),
                    'episode_title': meta.get('episode_title', ''),
                    'thumbnail': meta.get('thumbnail', ''),
                    'fanart': meta.get('fanart', ''),
                    'description': meta.get('description', ''),
                }
        return next_info

    def show_dialog(self, next_info):
        try:
            import xbmcaddon
            addon = xbmcaddon.Addon()
            dialog = UpNextDialog(
                'upnext-dialog.xml',
                addon.getAddonInfo('path'),
                'default',
                '1080i',
                next_episode_info=next_info,
                countdown_seconds=self.countdown_seconds,
            )
            dialog.doModal()
            del dialog
        except Exception:
            pass

    def _parse_episode_format(self, text):
        import re
        if not text:
            return None, None, None
        match = re.match(r'^(\d+)x(\d+)\s*(.*)', text)
        if match:
            return int(match.group(1)), int(match.group(2)), match.group(3).strip()
        return None, None, None

    def _get_next_from_playlist(self):
        try:
            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            current_position = playlist.getposition()
            if current_position >= (playlist.size() - 1):
                return None
            next_item = playlist[current_position + 1]
            if hasattr(next_item, 'getVideoInfoTag'):
                info_tag = next_item.getVideoInfoTag()
                return {
                    'serie_name': info_tag.getTVShowTitle() if hasattr(info_tag, 'getTVShowTitle') else '',
                    'original_name': info_tag.getOriginalTitle() if hasattr(info_tag, 'getOriginalTitle') else '',
                    'next_season': info_tag.getSeason() if hasattr(info_tag, 'getSeason') else 0,
                    'next_episode': info_tag.getEpisode() if hasattr(info_tag, 'getEpisode') else 0,
                    'episode_title': info_tag.getTitle() if hasattr(info_tag, 'getTitle') else '',
                    'thumbnail': next_item.getArt('thumb'),
                    'fanart': next_item.getArt('fanart'),
                    'description': info_tag.getPlot() if hasattr(info_tag, 'getPlot') else '',
                }
            else:
                label = next_item.getLabel()
                season, episode, episode_title = self._parse_episode_format(label)
                return {
                    'serie_name': '',
                    'next_season': season or 0,
                    'next_episode': episode or 0,
                    'episode_title': episode_title or label,
                    'thumbnail': next_item.getArt('thumb'),
                    'fanart': next_item.getArt('fanart'),
                    'description': '',
                }
        except Exception:
            return None
