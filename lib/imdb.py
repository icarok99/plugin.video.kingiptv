# -*- coding: utf-8 -*-
import re
import json
from bs4 import BeautifulSoup
try:
    from lib.ClientScraper import cfscraper
except ImportError:
    from ClientScraper import cfscraper
try:
    from lib.helper import *
except:
    from helper import *

def resize_poster(url, size='V1_QL100_UX1920'):
    # Substitui qualquer sufixo de tamanho existente pelo novo sufixo
    return re.sub(r'V1.*?(\.jpg)', size + r'\1', url)

class IMDBScraper:
    def __init__(self):
        self.base = 'https://www.imdb.com'
        self.headers = {
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8'
        }

    def soup(self, html):
        return BeautifulSoup(html, 'html.parser')

    def search_series(self, search):
        itens = []
        try:
            query = quote(search)
            url = f'{self.base}/find/?q={query}&s=tt&ttype=tv'
            html = cfscraper.get(url, headers=self.headers).text
            json_ = re.findall(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html, re.DOTALL)[0]
            data = json.loads(json_)
            results = data['props']['pageProps']['titleResults']['results']
            for idx, serie in enumerate(results):
                imdb_id = serie['id']
                page = f'{self.base}/title/{imdb_id}/?ref_=fn_tt_tt_{idx}'
                name = serie['titleNameText']
                year = serie.get('titleReleaseText', '0').split('-')[0]
                img_original = serie.get('titlePosterImageModel', {}).get('url', '')
                img = resize_poster(img_original)
                if not img:
                    continue
                name = name.replace('&', '&').replace('&apos;', "'")
                itens.append((name, img, page, year, imdb_id))
        except:
            pass
        return itens

    def series_250(self, page=1, per_page=250):
        itens = []
        try:
            url = self.base + '/chart/toptv/?ref_=nv_tvv_250'
            html = cfscraper.get(url, headers=self.headers).text
            json_ = re.findall(r'<script type="application/ld\+json">(.+?)</script>', html, re.DOTALL)[0]
            dict_ = json.loads(json_)
            all_items = []
            for i in dict_['itemListElement']:
                data = i['item']
                name = data.get('alternateName', data.get('name', ''))
                url = data['url']
                description = data.get('description', '')
                image = resize_poster(data.get('image', ''))
                if not image:
                    continue
                imdb_id = 'tt' + re.findall(r'/tt(.*?)/', url)[0]
                name = name.replace('&', '&').replace('&apos;', "'")
                description = description.replace('&', '&').replace('&apos;', "'")
                all_items.append((name, image, url, description, imdb_id))
            start = (page - 1) * per_page
            end = start + per_page
            itens = all_items[start:end]
        except:
            pass
        return itens

    def series_popular(self, page=1, per_page=100):
        itens = []
        try:
            url = self.base + '/chart/tvmeter/?ref_=nv_tvv_mptv'
            html = cfscraper.get(url, headers=self.headers).text
            json_ = re.findall(r'<script type="application/ld\+json">(.+?)</script>', html, re.DOTALL)[0]
            dict_ = json.loads(json_)
            all_items = []
            for i in dict_['itemListElement']:
                data = i['item']
                name = data.get('alternateName', data.get('name', ''))
                url = data['url']
                description = data.get('description', '')
                image = resize_poster(data.get('image', ''))
                if not image:
                    continue
                imdb_id = 'tt' + re.findall(r'/tt(.*?)/', url)[0]
                name = name.replace('&', '&').replace('&apos;', "'")
                description = description.replace('&', '&').replace('&apos;', "'")
                all_items.append((name, image, url, description, imdb_id))
            start = (page - 1) * per_page
            end = start + per_page
            itens = all_items[start:end]
        except:
            pass
        return itens

    def imdb_seasons(self, url):
        itens = []
        try:
            html = cfscraper.get(url, headers=self.headers).text
            json_ = re.findall(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html, re.DOTALL)[0]
            data = json.loads(json_)
            seasons = data['props']['pageProps']['mainColumnData']['episodes']['seasons']
            imdb_id = 'tt' + re.findall(r'/tt(.*?)/', url)[0]
            season_base_url = self.base + '/title/' + imdb_id + '/episodes/?season='
            for season in seasons:
                name = f"{season['number']} temporada"
                url_season = season_base_url + str(season['number'])
                itens.append((str(season['number']), name, url_season))
        except:
            pass
        return itens

    def imdb_episodes(self, url):
        itens = []
        try:
            html = cfscraper.get(url, headers=self.headers).text
            json_ = re.findall(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html, re.DOTALL)[0]
            data = json.loads(json_)
            episodes = data['props']['pageProps']['contentData']['section']['episodes']['items']
            fanart = data['props']['pageProps']['contentData']['entityMetadata'].get('primaryImage', {}).get('url', '')
            fanart = resize_poster(fanart)
            for idx, episode in enumerate(episodes, start=1):
                name = episode.get('titleText', f'Episodio - {idx}')
                img = resize_poster(episode.get('image', {}).get('url', ''))
                description = episode.get('plot', '')
                name = name.replace('&', '&').replace('&apos;', "'")
                description = description.replace('&', '&').replace('&apos;', "'")
                itens.append((str(idx), name, img, fanart, description))
        except:
            pass
        return itens

    def search_movies(self, search):
        itens = []
        try:
            query = quote(search)
            url = f'{self.base}/find/?q={query}&s=tt&ttype=ft'
            html = cfscraper.get(url, headers=self.headers).text
            json_ = re.findall(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html, re.DOTALL)[0]
            data = json.loads(json_)
            results = data['props']['pageProps']['titleResults']['results']
            for idx, movie in enumerate(results):
                imdb_id = movie['id']
                page = f'{self.base}/title/{imdb_id}/?ref_=fn_tt_tt_{idx}'
                name = movie['titleNameText']
                year = movie.get('titleReleaseText', '0').split('-')[0]
                img_original = movie.get('titlePosterImageModel', {}).get('url', '')
                img = resize_poster(img_original)
                if not img:
                    continue
                name = name.replace('&', '&').replace('&apos;', "'")
                itens.append((name, img, page, year, imdb_id))
        except:
            pass
        return itens

    def movies_250(self, page=1, per_page=250):
        itens = []
        try:
            url = self.base + '/chart/top/?ref_=nv_mv_250'
            html = cfscraper.get(url, headers=self.headers).text
            json_ = re.findall(r'<script type="application/ld\+json">(.+?)</script>', html, re.DOTALL)[0]
            dict_ = json.loads(json_)
            all_items = []
            for i in dict_['itemListElement']:
                data = i['item']
                name = data.get('alternateName', data.get('name', ''))
                url = data['url']
                description = data.get('description', '')
                image = resize_poster(data.get('image', ''))
                if not image:
                    continue
                imdb_id = 'tt' + re.findall(r'/tt(.*?)/', url)[0]
                name = name.replace('&', '&').replace('&apos;', "'")
                description = description.replace('&', '&').replace('&apos;', "'")
                all_items.append((name, image, url, description, imdb_id))
            start = (page - 1) * per_page
            end = start + per_page
            itens = all_items[start:end]
        except:
            pass
        return itens

    def movies_popular(self, page=1, per_page=100):
        itens = []
        try:
            url = self.base + '/chart/moviemeter/?ref_=nv_mv_mpm'
            html = cfscraper.get(url, headers=self.headers).text
            json_ = re.findall(r'<script type="application/ld\+json">(.+?)</script>', html, re.DOTALL)[0]
            dict_ = json.loads(json_)
            all_items = []
            for i in dict_['itemListElement']:
                data = i['item']
                name = data.get('alternateName', data.get('name', ''))
                url = data['url']
                description = data.get('description', '')
                image = resize_poster(data.get('image', ''))
                if not image:
                    continue
                imdb_id = 'tt' + re.findall(r'/tt(.*?)/', url)[0]
                name = name.replace('&', '&').replace('&apos;', "'")
                description = description.replace('&', '&').replace('&apos;', "'")
                all_items.append((name, image, url, description, imdb_id))
            start = (page - 1) * per_page
            end = start + per_page
            itens = all_items[start:end]
        except:
            pass
        return itens

