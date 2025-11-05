# -*- coding: utf-8 -*-
import re
import json
from urllib.parse import quote
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
    if not url:
        return ''
    return re.sub(r'V1.*?(\.jpg)', size + r'\1', url)


class IMDBScraper:
    def __init__(self):
        self.base = 'https://www.imdb.com'
        self.headers = {
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
        }

    def soup(self, html):
        return BeautifulSoup(html, 'html.parser')

    def _extract_next_data(self, html):
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

    def search_series(self, search):
        itens = []
        try:
            query = quote(search)
            url = f'{self.base}/find/?q={query}&s=tt&ttype=tv'
            response = cfscraper.get(url, headers=self.headers)

            if response.status_code != 200:
                return itens

            data = self._extract_next_data(response.text)
            if not data:
                return itens

            results = data.get('props', {}).get('pageProps', {}).get('titleResults', {}).get('results', [])
            for item in results:
                list_item = item.get('listItem', {})
                if not list_item:
                    continue

                imdb_id = item.get('index', '')
                if imdb_id.startswith('tt'):
                    imdb_id = imdb_id[2:]
                imdb_id = 'tt' + imdb_id

                name = list_item.get('titleText', '').strip()
                year = str(list_item.get('releaseYear', 0) or 0)
                img_original = list_item.get('primaryImage', {}).get('url', '')
                img = resize_poster(img_original)

                if not img or not name:
                    continue

                page = f'{self.base}/title/{imdb_id}/'
                name = name.replace('&', '&').replace("'", "'")
                itens.append((name, img, page, year, imdb_id))

        except Exception:
            pass

        return itens

    def search_movies(self, search):
        itens = []
        try:
            query = quote(search)
            url = f'{self.base}/find/?q={query}&s=tt&ttype=ft'
            response = cfscraper.get(url, headers=self.headers)

            if response.status_code != 200:
                return itens

            data = self._extract_next_data(response.text)
            if not data:
                return itens

            results = data.get('props', {}).get('pageProps', {}).get('titleResults', {}).get('results', [])
            for item in results:
                list_item = item.get('listItem', {})
                if not list_item:
                    continue

                imdb_id = item.get('index', '')
                if imdb_id.startswith('tt'):
                    imdb_id = imdb_id[2:]
                imdb_id = 'tt' + imdb_id

                name = list_item.get('titleText', '').strip()
                year = str(list_item.get('releaseYear', 0) or 0)
                img_original = list_item.get('primaryImage', {}).get('url', '')
                img = resize_poster(img_original)

                if not img or not name:
                    continue

                page = f'{self.base}/title/{imdb_id}/'
                name = name.replace('&', '&').replace("'", "'")
                itens.append((name, img, page, year, imdb_id))

        except Exception:
            pass

        return itens

    def series_250(self, page=1, per_page=250):
        return self._chart_parser('/chart/toptv/?ref_=nv_tvv_250', page, per_page)

    def series_popular(self, page=1, per_page=100):
        return self._chart_parser('/chart/tvmeter/?ref_=nv_tvv_mptv', page, per_page)

    def movies_250(self, page=1, per_page=250):
        return self._chart_parser('/chart/top/?ref_=nv_mv_250', page, per_page)

    def movies_popular(self, page=1, per_page=100):
        return self._chart_parser('/chart/moviemeter/?ref_=nv_mv_mpm', page, per_page)

    def _chart_parser(self, chart_path, page=1, per_page=100):
        itens = []
        try:
            url = self.base + chart_path
            html = cfscraper.get(url, headers=self.headers).text
            json_match = re.search(r'<script type="application/ld\+json">(.+?)</script>', html, re.DOTALL)
            if not json_match:
                return itens
            dict_ = json.loads(json_match.group(1))
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
                name = name.replace('&', '&').replace("'", "'")
                description = description.replace('&', '&').replace("'", "'")
                all_items.append((name, image, url, description, imdb_id))
            start = (page - 1) * per_page
            end = start + per_page
            itens = all_items[start:end]
        except Exception:
            pass
        return itens

    def imdb_seasons(self, url):
        itens = []
        try:
            html = cfscraper.get(url, headers=self.headers).text
            data = self._extract_next_data(html)
            if not data:
                return itens
            seasons = data['props']['pageProps']['mainColumnData']['episodes']['seasons']
            imdb_id = 'tt' + re.findall(r'/tt(.*?)/', url)[0]
            season_base_url = self.base + '/title/' + imdb_id + '/episodes/?season='
            for season in seasons:
                num = str(season['number'])
                name = f"{num} temporada"
                url_season = season_base_url + num
                itens.append((num, name, url_season))
        except Exception:
            pass
        return itens

    def imdb_episodes(self, url):
        itens = []
        try:
            html = cfscraper.get(url, headers=self.headers).text
            data = self._extract_next_data(html)
            if not data:
                return itens
            episodes = data['props']['pageProps']['contentData']['section']['episodes']['items']
            fanart = resize_poster(data['props']['pageProps']['contentData']['entityMetadata'].get('primaryImage', {}).get('url', ''))
            for idx, ep in enumerate(episodes, start=1):
                name = ep.get('titleText', f'Episódio {idx}')
                img = resize_poster(ep.get('image', {}).get('url', ''))
                description = ep.get('plot', '')
                name = name.replace('&', '&').replace("'", "'")
                description = description.replace('&', '&').replace("'", "'")
                itens.append((str(idx), name, img, fanart, description))
        except Exception:
            pass
        return itens
