# -*- coding: utf-8 -*-

import sqlite3
import xbmcvfs
import xbmcaddon
import xbmc
import os
from contextlib import contextmanager
from datetime import datetime

ADDON = xbmcaddon.Addon()
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_DATA = xbmcvfs.translatePath('special://profile/addon_data/{}/'.format(ADDON_ID))
DATABASE_PATH = os.path.join(ADDON_DATA, 'kingiptv.db')

if not xbmcvfs.exists(ADDON_DATA):
    xbmcvfs.mkdirs(ADDON_DATA)


class KingDatabase:

    def __init__(self):
        self.db_path = DATABASE_PATH
        try:
            self._init_database()
        except Exception:
            raise

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_database(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS episodes_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    imdb_id TEXT NOT NULL,
                    season INTEGER NOT NULL,
                    episode INTEGER NOT NULL,
                    episode_title TEXT,
                    description TEXT,
                    thumbnail TEXT,
                    fanart TEXT,
                    serie_name TEXT,
                    original_name TEXT,
                    is_last_episode TEXT DEFAULT 'no',
                    created_at TEXT,
                    updated_at TEXT,
                    UNIQUE(imdb_id, season, episode)
                )
            ''')

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metadata_imdb_season ON episodes_metadata(imdb_id, season)')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS watched_episodes (
                    imdb_id TEXT NOT NULL,
                    season  INTEGER NOT NULL,
                    episode INTEGER NOT NULL,
                    watched_at TEXT,
                    PRIMARY KEY (imdb_id, season, episode)
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_watched_imdb_season ON watched_episodes(imdb_id, season)')

            cursor.execute("PRAGMA table_info(episodes_metadata)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'is_last_episode' not in columns:
                cursor.execute('''
                    ALTER TABLE episodes_metadata
                    ADD COLUMN is_last_episode TEXT DEFAULT 'no'
                ''')

    def get_next_episode_metadata(self, imdb_id, current_season, current_episode):
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
                SELECT * FROM episodes_metadata
                WHERE imdb_id = ? AND season = ? AND episode IN (?, ?)
                ORDER BY episode
            ''', (imdb_id, current_season, current_episode, current_episode + 1))

            rows = cursor.fetchall()

            if not rows:
                return None

            current_ep = None
            next_ep = None

            for row in rows:
                row_dict = dict(row)
                if row_dict['episode'] == current_episode:
                    current_ep = row_dict
                elif row_dict['episode'] == current_episode + 1:
                    next_ep = row_dict

            if current_ep and current_ep.get('is_last_episode') == 'yes':
                return None

            return next_ep

    def save_season_episodes(self, imdb_id, season, serie_name, original_name, episodes_data, last_episode_num=None):
        if not episodes_data:
            return

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if last_episode_num is None:
            last_episode_num = max([int(ep[0]) for ep in episodes_data])

        with self._get_connection() as conn:
            cursor = conn.cursor()

            batch_data = []
            for episode_num, title, thumbnail, fanart, description in episodes_data:
                episode_num = int(episode_num)
                is_last = 'yes' if episode_num == last_episode_num else 'no'

                batch_data.append((
                    imdb_id,
                    season,
                    episode_num,
                    title,
                    description,
                    thumbnail,
                    fanart,
                    serie_name,
                    original_name,
                    is_last,
                    now,
                    now
                ))

            cursor.executemany('''
                INSERT INTO episodes_metadata
                (imdb_id, season, episode, episode_title, description,
                 thumbnail, fanart, serie_name, original_name, is_last_episode,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(imdb_id, season, episode)
                DO UPDATE SET
                    episode_title = excluded.episode_title,
                    description = excluded.description,
                    thumbnail = excluded.thumbnail,
                    fanart = excluded.fanart,
                    serie_name = excluded.serie_name,
                    original_name = excluded.original_name,
                    is_last_episode = excluded.is_last_episode,
                    updated_at = excluded.updated_at
            ''', batch_data)

    def get_season_episodes(self, imdb_id, season):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM episodes_metadata
                WHERE imdb_id = ? AND season = ?
                ORDER BY episode
            ''', (imdb_id, season))

            episodes = []
            for row in cursor.fetchall():
                episodes.append(dict(row))

            return episodes

    def get_episode_metadata(self, imdb_id, season, episode):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM episodes_metadata
                WHERE imdb_id = ? AND season = ? AND episode = ?
            ''', (imdb_id, season, episode))

            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def mark_watched(self, imdb_id, season, episode):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self._get_connection() as conn:
            conn.cursor().execute('''
                INSERT OR REPLACE INTO watched_episodes (imdb_id, season, episode, watched_at)
                VALUES (?, ?, ?, ?)
            ''', (imdb_id, int(season), int(episode), now))

    def is_watched(self, imdb_id, season, episode):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 1 FROM watched_episodes
                WHERE imdb_id = ? AND season = ? AND episode = ?
            ''', (imdb_id, int(season), int(episode)))
            return cursor.fetchone() is not None

    def get_watched_in_season(self, imdb_id, season):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT episode FROM watched_episodes
                WHERE imdb_id = ? AND season = ?
            ''', (imdb_id, int(season)))
            return {row[0] for row in cursor.fetchall()}
