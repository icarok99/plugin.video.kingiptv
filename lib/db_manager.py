# -*- coding: utf-8 -*-

import os
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
from datetime import datetime, timedelta

ADDON_ID      = 'plugin.video.kingiptv'
ADDON         = xbmcaddon.Addon(ADDON_ID)
ADDON_DATA    = xbmcvfs.translatePath('special://profile/addon_data/{}/'.format(ADDON_ID))
DATABASE_PATH = os.path.join(ADDON_DATA, 'kingiptv.db')


def notify(message, time_ms=4000):
    xbmc.executebuiltin('Notification(KingIPTV, {}, {}, {})'.format(
        message, time_ms, ADDON.getAddonInfo('icon')
    ))


class KingDatabaseManager:

    def _db_exists(self):
        return os.path.isfile(DATABASE_PATH)

    def _get_setting_int(self, key, default=7):
        try:
            return int(ADDON.getSetting(key))
        except (ValueError, TypeError):
            return default

    def _get_setting_bool(self, key):
        return ADDON.getSetting(key).lower() == 'true'

    def _last_modified_date(self):
        try:
            return datetime.fromtimestamp(os.path.getmtime(DATABASE_PATH))
        except OSError:
            return None

    def delete_database(self, confirm=True):
        if not self._db_exists():
            return False

        if confirm:
            ok = xbmcgui.Dialog().yesno('KingIPTV', ADDON.getLocalizedString(33004))
            if not ok:
                return False

        try:
            os.remove(DATABASE_PATH)
        except Exception:
            try:
                xbmcvfs.delete(DATABASE_PATH)
            except Exception:
                pass

        if self._db_exists():
            notify('Falha ao excluir o banco de dados.')
            return False

        notify('Banco de dados excluído com sucesso.')
        return True

    def check_auto_expiry(self):
        if not self._get_setting_bool('db_auto_cleanup_enabled'):
            return

        if not self._db_exists():
            return

        expiry_days   = self._get_setting_int('db_cleanup_days', default=7)
        last_modified = self._last_modified_date()

        if last_modified is None:
            return

        if expiry_days == 0 or datetime.now() - last_modified >= timedelta(days=expiry_days):
            self.delete_database(confirm=False)


if __name__ == '__main__':
    KingDatabaseManager().delete_database(confirm=True)
