# -*- coding: utf-8 -*-

import sqlite3
import xbmcvfs
import xbmcaddon
import xbmc
import os
from contextlib import contextmanager
from datetime import datetime

ADDON      = xbmcaddon.Addon()
ADDON_ID   = ADDON.getAddonInfo('id')
ADDON_DATA = xbmcvfs.translatePath(
    'special://profile/addon_data/{}/'.format(ADDON_ID)
)
DATABASE_PATH = os.path.join(ADDON_DATA, 'kingiptv.db')

if not xbmcvfs.exists(ADDON_DATA):
    xbmcvfs.mkdirs(ADDON_DATA)


class KingDatabase:

    def __init__(self):
        self.db_path = DATABASE_PATH
        self._init_database()

    # ── connection ─────────────────────────────────────────────────────────────

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── schema init + migration ────────────────────────────────────────────────

    def _init_database(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('PRAGMA journal_mode=WAL')

            # ── slug → imdb_id mapping (new) ───────────────────────────────────
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS slug_imdb_map (
                    slug    TEXT PRIMARY KEY,
                    imdb_id TEXT NOT NULL,
                    updated_at TEXT
                )
            ''')

            # ── episodes_metadata ──────────────────────────────────────────────
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS episodes_metadata (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug          TEXT    NOT NULL,
                    season        INTEGER NOT NULL,
                    episode       INTEGER NOT NULL,
                    episode_title TEXT,
                    description   TEXT,
                    thumbnail     TEXT,
                    fanart        TEXT,
                    serie_name    TEXT,
                    original_name TEXT,
                    is_last_episode TEXT DEFAULT 'no',
                    created_at    TEXT,
                    updated_at    TEXT,
                    UNIQUE(slug, season, episode)
                )
            ''')
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_metadata_slug_season '
                'ON episodes_metadata(slug, season)'
            )

            # ── watched_episodes ───────────────────────────────────────────────
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS watched_episodes (
                    slug       TEXT    NOT NULL,
                    season     INTEGER NOT NULL,
                    episode    INTEGER NOT NULL,
                    watched_at TEXT,
                    PRIMARY KEY (slug, season, episode)
                )
            ''')
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_watched_slug_season '
                'ON watched_episodes(slug, season)'
            )

            # ── skip_timestamps ────────────────────────────────────────────────
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS skip_timestamps (
                    slug        TEXT    NOT NULL,
                    season      INTEGER NOT NULL,
                    episode     INTEGER NOT NULL,
                    intro_start REAL,
                    intro_end   REAL,
                    source      TEXT    DEFAULT 'introhater',
                    updated_at  TEXT,
                    PRIMARY KEY (slug, season, episode)
                )
            ''')
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_skip_slug '
                'ON skip_timestamps(slug)'
            )

            # ── migrate legacy imdb_id columns → slug ──────────────────────────
            self._migrate_legacy(cursor)

    def _migrate_legacy(self, cursor):
        """Rename legacy `imdb_id` column to `slug` in all three tables."""
        tables = [
            ('episodes_metadata', 'imdb_id', 'slug'),
            ('watched_episodes',  'imdb_id', 'slug'),
            ('skip_timestamps',   'imdb_id', 'slug'),
        ]
        for table, old_col, new_col in tables:
            cursor.execute('PRAGMA table_info({})'.format(table))
            cols = [row[1] for row in cursor.fetchall()]
            if old_col in cols and new_col not in cols:
                # SQLite < 3.25 does not support RENAME COLUMN, so rebuild
                cursor.execute(
                    'ALTER TABLE {} RENAME TO _{}_old'.format(table, table)
                )
                # The CREATE TABLE already ran above (it uses the new schema),
                # so just copy data across, mapping old column name to new.
                cursor.execute(
                    'INSERT INTO {tbl} SELECT * FROM _{tbl}_old'.format(
                        tbl=table
                    )
                )
                cursor.execute('DROP TABLE IF EXISTS _{}_old'.format(table))
            elif old_col in cols and new_col in cols:
                # Both exist — drop the old one (shouldn't happen normally)
                pass

    # ── slug ↔ imdb_id mapping ─────────────────────────────────────────────────

    def get_imdb_id(self, slug):
        """Return the IMDb ID stored for *slug*, or ``None``."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT imdb_id FROM slug_imdb_map WHERE slug = ?', (slug,)
            )
            row = cursor.fetchone()
            return row['imdb_id'] if row else None

    def save_imdb_id(self, slug, imdb_id):
        """Persist the *slug* → *imdb_id* mapping."""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self._get_connection() as conn:
            conn.cursor().execute(
                '''
                INSERT INTO slug_imdb_map (slug, imdb_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    imdb_id    = excluded.imdb_id,
                    updated_at = excluded.updated_at
                ''',
                (slug, imdb_id, now)
            )

    # ── episodes metadata ──────────────────────────────────────────────────────

    def get_next_episode_metadata(self, slug, current_season, current_episode):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM episodes_metadata
                WHERE slug = ? AND season = ? AND episode IN (?, ?)
                ORDER BY episode
            ''', (slug, current_season, current_episode, current_episode + 1))

            current_ep = next_ep = None
            for row in cursor.fetchall():
                d = dict(row)
                if d['episode'] == current_episode:
                    current_ep = d
                elif d['episode'] == current_episode + 1:
                    next_ep = d

            if current_ep and current_ep.get('is_last_episode') == 'yes':
                return None
            return next_ep

    def save_season_episodes(
        self, slug, season, serie_name, original_name,
        episodes_data, last_episode_num=None
    ):
        if not episodes_data:
            return

        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if last_episode_num is None:
            last_episode_num = max(int(ep[0]) for ep in episodes_data)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            batch = []
            for episode_num, title, thumbnail, fanart, description in episodes_data:
                episode_num = int(episode_num)
                batch.append((
                    slug, season, episode_num,
                    title, description, thumbnail, fanart,
                    serie_name, original_name,
                    'yes' if episode_num == last_episode_num else 'no',
                    now, now,
                ))
            cursor.executemany('''
                INSERT INTO episodes_metadata
                    (slug, season, episode, episode_title, description,
                     thumbnail, fanart, serie_name, original_name,
                     is_last_episode, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug, season, episode) DO UPDATE SET
                    episode_title   = excluded.episode_title,
                    description     = excluded.description,
                    thumbnail       = excluded.thumbnail,
                    fanart          = excluded.fanart,
                    serie_name      = excluded.serie_name,
                    original_name   = excluded.original_name,
                    is_last_episode = excluded.is_last_episode,
                    updated_at      = excluded.updated_at
            ''', batch)

    def get_season_episodes(self, slug, season):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM episodes_metadata
                WHERE slug = ? AND season = ?
                ORDER BY episode
            ''', (slug, int(season)))
            return [dict(row) for row in cursor.fetchall()]

    def get_episode_metadata(self, slug, season, episode):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM episodes_metadata
                WHERE slug = ? AND season = ? AND episode = ?
            ''', (slug, int(season), int(episode)))
            row = cursor.fetchone()
            return dict(row) if row else None

    # ── watched episodes ───────────────────────────────────────────────────────

    def mark_watched(self, slug, season, episode):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self._get_connection() as conn:
            conn.cursor().execute('''
                INSERT OR REPLACE INTO watched_episodes
                    (slug, season, episode, watched_at)
                VALUES (?, ?, ?, ?)
            ''', (slug, int(season), int(episode), now))

    def is_watched(self, slug, season, episode):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 1 FROM watched_episodes
                WHERE slug = ? AND season = ? AND episode = ?
            ''', (slug, int(season), int(episode)))
            return cursor.fetchone() is not None

    def get_watched_in_season(self, slug, season):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT episode FROM watched_episodes
                WHERE slug = ? AND season = ?
            ''', (slug, int(season)))
            return {row[0] for row in cursor.fetchall()}

    # ── skip timestamps ────────────────────────────────────────────────────────

    def get_skip_timestamps(self, slug, season, episode):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT intro_start, intro_end, source
                FROM skip_timestamps
                WHERE slug = ? AND season = ? AND episode = ?
                ORDER BY CASE source WHEN 'manual' THEN 0 ELSE 1 END
                LIMIT 1
            ''', (slug, int(season), int(episode)))
            row = cursor.fetchone()
            if not row:
                return None
            result = {k: v for k, v in zip(
                ('intro_start', 'intro_end', 'source'), row
            ) if v is not None}
            return result if len(result) > 1 else None

    def save_skip_timestamps(
        self, slug, season, episode,
        intro_start=None, intro_end=None,
        source='introhater', **_extra
    ):
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if source == 'manual':
                cursor.execute('''
                    INSERT INTO skip_timestamps
                        (slug, season, episode,
                         intro_start, intro_end, source, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'manual', ?)
                    ON CONFLICT(slug, season, episode) DO UPDATE SET
                        intro_start = COALESCE(excluded.intro_start, intro_start),
                        intro_end   = COALESCE(excluded.intro_end,   intro_end),
                        source      = 'manual',
                        updated_at  = excluded.updated_at
                ''', (slug, int(season), int(episode),
                      intro_start, intro_end, now))
            else:
                cursor.execute('''
                    INSERT INTO skip_timestamps
                        (slug, season, episode,
                         intro_start, intro_end, source, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'introhater', ?)
                    ON CONFLICT(slug, season, episode) DO UPDATE SET
                        intro_start = CASE WHEN source = 'manual'
                                          THEN intro_start
                                          ELSE COALESCE(excluded.intro_start, intro_start) END,
                        intro_end   = CASE WHEN source = 'manual'
                                          THEN intro_end
                                          ELSE COALESCE(excluded.intro_end, intro_end) END,
                        source      = CASE WHEN source = 'manual'
                                          THEN 'manual' ELSE 'introhater' END,
                        updated_at  = CASE WHEN source = 'manual'
                                          THEN updated_at ELSE excluded.updated_at END
                ''', (slug, int(season), int(episode),
                      intro_start, intro_end, now))

    def skip_timestamps_checked(self, slug, season, episode):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT 1 FROM skip_timestamps '
                'WHERE slug = ? AND season = ? AND episode = ?',
                (slug, int(season), int(episode))
            )
            return cursor.fetchone() is not None

    def save_skip_timestamps_batch(
        self, slug, season, episodes_data, source='introhater'
    ):
        if not episodes_data:
            return 0

        now   = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        batch = []
        for ep in episodes_data:
            episode = int(ep.get('episode', 0))
            if episode <= 0:
                continue
            batch.append((
                slug, int(season), episode,
                ep.get('intro_start'), ep.get('intro_end'), now,
            ))

        if not batch:
            return 0

        with self._get_connection() as conn:
            cursor = conn.cursor()
            if source == 'manual':
                cursor.executemany('''
                    INSERT INTO skip_timestamps
                        (slug, season, episode,
                         intro_start, intro_end, source, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'manual', ?)
                    ON CONFLICT(slug, season, episode) DO UPDATE SET
                        intro_start = COALESCE(excluded.intro_start, intro_start),
                        intro_end   = COALESCE(excluded.intro_end,   intro_end),
                        source      = 'manual',
                        updated_at  = excluded.updated_at
                ''', batch)
            else:
                cursor.executemany('''
                    INSERT INTO skip_timestamps
                        (slug, season, episode,
                         intro_start, intro_end, source, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'introhater', ?)
                    ON CONFLICT(slug, season, episode) DO UPDATE SET
                        intro_start = CASE WHEN source = 'manual'
                                          THEN intro_start
                                          ELSE COALESCE(excluded.intro_start, intro_start) END,
                        intro_end   = CASE WHEN source = 'manual'
                                          THEN intro_end
                                          ELSE COALESCE(excluded.intro_end, intro_end) END,
                        source      = CASE WHEN source = 'manual'
                                          THEN 'manual' ELSE 'introhater' END,
                        updated_at  = CASE WHEN source = 'manual'
                                          THEN updated_at ELSE excluded.updated_at END
                ''', batch)

        return len(batch)
