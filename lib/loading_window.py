import xbmc
import xbmcgui
import xbmcaddon
import threading
import time
import os


class _PlaybackMonitor(xbmc.Player):

    def __init__(self):
        super().__init__()
        self._event = threading.Event()

    def onPlayBackStarted(self):
        self._event.set()

    def onAVStarted(self):
        self._event.set()

    def onPlayBackError(self):
        self._event.set()

    def onPlayBackStopped(self):
        self._event.set()

    def reset(self):
        self._event.clear()

    def wait_for_playback(self, timeout=20):
        monitor = xbmc.Monitor()
        elapsed = 0
        interval = 0.2

        while elapsed < timeout:
            if self._event.is_set():
                return True
            try:
                if self.isPlaying() and self.getTime() > 0:
                    return True
            except:
                pass
            if monitor.waitForAbort(interval):
                return False
            elapsed += interval

        return False


class LoadingWindow(xbmcgui.WindowXMLDialog):
    
    PROGRESS_CONTROL = 100
    
    def __init__(self, *args, **kwargs):
        self.progress = 0
        self.closing = False
        self._progress_thread = None
        self._controls_ready = False
        
    def onInit(self):
        try:
            self._controls_ready = True
            xbmcgui.Window(10000).clearProperty('loading.phase2')
            self.start_progress_animation()
        except Exception as e:
            pass
    
    def start_progress_animation(self):
        if self._progress_thread is None or not self._progress_thread.is_alive():
            self.closing = False
            self._progress_thread = threading.Thread(target=self._animate_progress)
            self._progress_thread.daemon = True
            self._progress_thread.start()
    
    def _animate_progress(self):
        try:
            while not self.closing:
                for i in range(0, 101, 2):
                    if self.closing:
                        break
                    
                    if self._controls_ready:
                        try:
                            self.getControl(self.PROGRESS_CONTROL).setPercent(i)
                        except:
                            pass
                    
                    xbmcgui.Window(10000).setProperty('loading.progress', str(i))
                    time.sleep(0.05)
                
                if not self.closing:
                    time.sleep(0.2)
        except Exception as e:
            pass
    
    def set_phase2(self):
        try:
            xbmcgui.Window(10000).setProperty('loading.phase2', 'true')
        except Exception as e:
            pass
    
    def close_dialog(self):
        try:
            self.closing = True
            
            if self._progress_thread and self._progress_thread.is_alive():
                self._progress_thread.join(timeout=1.0)
            
            xbmcgui.Window(10000).clearProperty('loading.phase2')
            xbmcgui.Window(10000).clearProperty('loading.progress')
            xbmcgui.Window(10000).clearProperty('loading.fanart')
            
            self.close()
        except Exception as e:
            pass


class LoadingManager:
    
    def __init__(self):
        self.window = None
        self._lock = threading.Lock()
        self._monitor_thread = None
        self._should_close = False
        self._busy_suppress_thread = None
        self._suppress_busy = False
        self._player_monitor = _PlaybackMonitor()
    
    def _run_busy_suppressor(self):
        while self._suppress_busy:
            try:
                xbmc.executebuiltin('Dialog.Close(busydialog,true)')
                xbmc.executebuiltin('Dialog.Close(busydialognocancel,true)')
            except:
                pass
            xbmc.sleep(100)

    def show(self, fanart_path=None):
        with self._lock:
            try:
                if self.window:
                    try:
                        self.window.close_dialog()
                    except:
                        pass
                    self.window = None
                
                addon = xbmcaddon.Addon()
                addon_path = addon.getAddonInfo('path')
                
                if fanart_path is None:
                    fanart_path = os.path.join(addon_path, 'resources', 'skins', 'Default', 'media', 'fanart.jpg')
                
                xbmcgui.Window(10000).setProperty('loading.fanart', fanart_path)
                
                self._should_close = False
                self._suppress_busy = True
                self._busy_suppress_thread = threading.Thread(target=self._run_busy_suppressor)
                self._busy_suppress_thread.daemon = True
                self._busy_suppress_thread.start()
                
                self.window = LoadingWindow(
                    'DialogLoadingKing.xml',
                    addon_path,
                    'Default',
                    '1080i'
                )
                self.window.show()
                xbmc.sleep(100)
                
            except Exception as e:
                pass
    
    def set_phase2(self):
        if self.window:
            try:
                self.window.set_phase2()
            except Exception as e:
                pass
    
    def close(self):
        if self.window:
            self._should_close = True
            if self._monitor_thread is None or not self._monitor_thread.is_alive():
                self._player_monitor.reset()
                self._monitor_thread = threading.Thread(target=self._wait_for_playback)
                self._monitor_thread.daemon = True
                self._monitor_thread.start()

    def _wait_for_playback(self):
        self._player_monitor.wait_for_playback(timeout=20)
        with self._lock:
            if self.window and self._should_close:
                try:
                    self._suppress_busy = False
                    self.window.close_dialog()
                    self.window = None
                except Exception as e:
                    pass

    def force_close(self):
        with self._lock:
            self._suppress_busy = False
            self._should_close = False
            if self.window:
                try:
                    self.window.close_dialog()
                    self.window = None
                except Exception as e:
                    pass


loading_manager = LoadingManager()
