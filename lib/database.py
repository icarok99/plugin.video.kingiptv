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
        xbmc.log('KING IPTV DB - Inicializando database em: {}'.format(self.db_path), xbmc.LOGINFO)
        try:
            self._init_database()
            xbmc.log('KING IPTV DB - Database inicializado com sucesso', xbmc.LOGINFO)
        except Exception as e:
            xbmc.log('KING IPTV DB - ERRO ao inicializar database: {}'.format(str(e)), xbmc.LOGERROR)
            import traceback
            xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
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
            
            # Tabela de progresso dos episódios (rastreamento de tempo)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS episodes_progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    imdb_id TEXT NOT NULL,
                    season INTEGER NOT NULL,
                    episode INTEGER NOT NULL,
                    title TEXT,
                    current_time REAL DEFAULT 0,
                    total_time REAL DEFAULT 0,
                    watched_percent REAL DEFAULT 0,
                    thumbnail TEXT,
                    fanart TEXT,
                    last_played TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    UNIQUE(imdb_id, season, episode)
                )
            ''')
            
            # Tabela para rastrear qual episódio está sendo assistido atualmente
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS episode_watching (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    imdb_id TEXT NOT NULL UNIQUE,
                    serie_name TEXT,
                    original_name TEXT,
                    current_season INTEGER NOT NULL,
                    current_episode INTEGER NOT NULL,
                    next_season INTEGER,
                    next_episode INTEGER,
                    thumbnail TEXT,
                    fanart TEXT,
                    last_played TEXT,
                    updated_at TEXT
                )
            ''')
            
            # Tabela de metadados dos episódios
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
                    created_at TEXT,
                    updated_at TEXT,
                    UNIQUE(imdb_id, season, episode)
                )
            ''')
            
            # Criar índices para melhorar performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_episodes_imdb ON episodes_progress(imdb_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_watching_imdb ON episode_watching(imdb_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metadata_imdb_season ON episodes_metadata(imdb_id, season)')
            
            xbmc.log('KING IPTV DB - Todas as tabelas e índices criados com sucesso', xbmc.LOGINFO)
    
    def save_episode_progress(self, imdb_id, season, episode, current_time, total_time,
                             title='', thumbnail='', fanart='', serie_name='', original_name=''):
        """Salva progresso do episódio e atualiza qual episódio está sendo assistido"""
        watched_percent = (current_time / total_time * 100) if total_time > 0 else 0
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        xbmc.log('KING IPTV DB - Salvando progresso: {} S{}E{} - {}s/{}s ({}%)'.format(
            serie_name or title, season, episode, int(current_time), int(total_time), int(watched_percent)
        ), xbmc.LOGINFO)
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Salvar progresso do episódio
                cursor.execute('''
                    INSERT INTO episodes_progress 
                    (imdb_id, season, episode, title, current_time, total_time, 
                     watched_percent, thumbnail, fanart, last_played, 
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(imdb_id, season, episode) 
                    DO UPDATE SET
                        current_time = excluded.current_time,
                        total_time = excluded.total_time,
                        watched_percent = excluded.watched_percent,
                        last_played = excluded.last_played,
                        updated_at = excluded.updated_at
                ''', (imdb_id, season, episode, title, current_time, total_time,
                      watched_percent, thumbnail, fanart, now, now, now))
                
                xbmc.log('KING IPTV DB - Progresso salvo na tabela episodes_progress', xbmc.LOGINFO)
                
                # Calcular próximo episódio
                cursor.execute('''
                    SELECT season, episode
                    FROM episodes_metadata
                    WHERE imdb_id = ?
                        AND (season > ? OR (season = ? AND episode > ?))
                    ORDER BY season ASC, episode ASC
                    LIMIT 1
                ''', (imdb_id, season, season, episode))
                
                next_row = cursor.fetchone()
                if next_row:
                    next_season, next_episode = next_row[0], next_row[1]
                else:
                    # Se não houver próximo episódio, assumir episódio+1
                    next_season = season
                    next_episode = episode + 1
                
                # Atualizar episode_watching
                cursor.execute('''
                    INSERT INTO episode_watching
                    (imdb_id, serie_name, original_name, current_season, current_episode,
                     next_season, next_episode, thumbnail, fanart, last_played, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(imdb_id)
                    DO UPDATE SET
                        current_season = excluded.current_season,
                        current_episode = excluded.current_episode,
                        next_season = excluded.next_season,
                        next_episode = excluded.next_episode,
                        thumbnail = excluded.thumbnail,
                        fanart = excluded.fanart,
                        last_played = excluded.last_played,
                        updated_at = excluded.updated_at
                ''', (imdb_id, serie_name, original_name, season, episode,
                      next_season, next_episode, thumbnail, fanart, now, now))
                
                xbmc.log('KING IPTV DB - Episode watching atualizado: S{}E{} -> próximo S{}E{}'.format(
                    season, episode, next_season, next_episode
                ), xbmc.LOGINFO)
                
        except Exception as e:
            xbmc.log('KING IPTV DB - Erro ao salvar progresso: {}'.format(str(e)), xbmc.LOGERROR)
            import traceback
            xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
            raise
    
    def get_episode_progress(self, imdb_id, season, episode):
        """Retorna o progresso de um episódio específico"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM episodes_progress
                WHERE imdb_id = ? AND season = ? AND episode = ?
            ''', (imdb_id, season, episode))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def get_episode_watching(self, imdb_id):
        """Retorna informações sobre qual episódio está sendo assistido"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM episode_watching
                WHERE imdb_id = ?
            ''', (imdb_id,))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    
    def save_season_episodes(self, imdb_id, season, serie_name, original_name, episodes_data):
        """Salva metadados dos episódios de uma temporada"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            for episode_num, title, thumbnail, fanart, description in episodes_data:
                cursor.execute('''
                    INSERT INTO episodes_metadata
                    (imdb_id, season, episode, episode_title, description, 
                     thumbnail, fanart, serie_name, original_name, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(imdb_id, season, episode)
                    DO UPDATE SET
                        episode_title = excluded.episode_title,
                        description = excluded.description,
                        thumbnail = excluded.thumbnail,
                        fanart = excluded.fanart,
                        serie_name = excluded.serie_name,
                        original_name = excluded.original_name,
                        updated_at = excluded.updated_at
                ''', (imdb_id, season, int(episode_num), title, description,
                      thumbnail, fanart, serie_name, original_name, now, now))
    
    def get_season_episodes(self, imdb_id, season):
        """Retorna os episódios de uma temporada"""
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
        """Retorna metadados de um episódio"""
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