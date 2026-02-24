# -*- coding: utf-8 -*-
import re
import json
import html
from urllib.parse import quote
from bs4 import BeautifulSoup

try:
    from lib.helper import requests
except:
    from helper import requests


def resize_poster(url, size='V1_QL100_UX1920'):
    if not url:
        return ''
    return re.sub(r'V1.*?(\.jpg)', size + r'\1', url)


class IMDBScraper:
    def __init__(self):
        self.base = 'https://m.imdb.com'
        self.headers = {
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
        }

    def soup(self, html_text):
        return BeautifulSoup(html_text, 'html.parser')

    def _extract_next_data(self, html_text):
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
                          html_text, re.DOTALL)
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
            response = requests.get(url, headers=self.headers)

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

                title_obj = list_item.get('titleText', {})
                if isinstance(title_obj, dict):
                    serie_name = html.unescape(str(title_obj.get('text', '')).strip())
                else:
                    serie_name = html.unescape(str(title_obj).strip()) if title_obj else ''

                original_title_obj = list_item.get('originalTitleText', {})
                if isinstance(original_title_obj, dict):
                    original_name = html.unescape(str(original_title_obj.get('text', '')).strip())
                else:
                    original_name = html.unescape(str(original_title_obj).strip()) if original_title_obj else ''

                if not serie_name:
                    serie_name = original_name

                year = str(list_item.get('releaseYear', 0) or 0)
                img_original = list_item.get('primaryImage', {}).get('url', '')
                img = resize_poster(img_original)

                plot_obj = list_item.get('plot', {})
                if isinstance(plot_obj, dict):
                    description = html.unescape(str(plot_obj.get('text', '')).strip())
                else:
                    description = html.unescape(str(plot_obj).strip()) if plot_obj else ''

                if not img or not serie_name:
                    continue

                page = f'{self.base}/title/{imdb_id}/'
                itens.append((serie_name, img, page, description, imdb_id, original_name, year))

        except Exception:
            pass

        return itens

    def search_movies(self, search):
        itens = []
        try:
            query = quote(search)
            url = f'{self.base}/find/?q={query}&s=tt&ttype=movie'
            response = requests.get(url, headers=self.headers)

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

                title_obj = list_item.get('titleText', {})
                if isinstance(title_obj, dict):
                    movie_name = html.unescape(str(title_obj.get('text', '')).strip())
                else:
                    movie_name = html.unescape(str(title_obj).strip()) if title_obj else ''

                original_title_obj = list_item.get('originalTitleText', {})
                if isinstance(original_title_obj, dict):
                    original_name = html.unescape(str(original_title_obj.get('text', '')).strip())
                else:
                    original_name = html.unescape(str(original_title_obj).strip()) if original_title_obj else ''

                if not movie_name:
                    movie_name = original_name

                year = str(list_item.get('releaseYear', 0) or 0)
                img_original = list_item.get('primaryImage', {}).get('url', '')
                img = resize_poster(img_original)

                plot_obj = list_item.get('plot', {})
                if isinstance(plot_obj, dict):
                    description = html.unescape(str(plot_obj.get('text', '')).strip())
                else:
                    description = html.unescape(str(plot_obj).strip()) if plot_obj else ''

                if not img or not movie_name:
                    continue

                page = f'{self.base}/title/{imdb_id}/'
                itens.append((movie_name, img, page, description, imdb_id, original_name, year))

        except Exception:
            pass

        return itens

    def series_250(self, page=1, per_page=250):
        return self._chart_parser('/pt/chart/toptv/?ref_=chttvm_nv_menu', page, per_page, content_type='series')

    def series_popular(self, page=1, per_page=100):
        return self._chart_parser('/pt/chart/tvmeter/?ref_=chtmvm_nv_menu', page, per_page, content_type='series')

    def movies_250(self, page=1, per_page=250):
        return self._chart_parser('/pt/chart/top/?ref_=chtmvm_nv_menu', page, per_page, content_type='movie')

    def movies_popular(self, page=1, per_page=100):
        return self._chart_parser('/pt/chart/moviemeter/?ref_=chttp_nv_menu', page, per_page, content_type='movie')

    def _chart_parser(self, chart_path, page=1, per_page=100, content_type='movie'):
        itens = []
        try:
            url = self.base + chart_path
            response = requests.get(url, headers=self.headers)
            html_text = response.text
            json_match = re.search(r'<script type="application/ld\+json">(.+?)</script>',
                                   html_text, re.DOTALL)
            if not json_match:
                return itens

            dict_ = json.loads(json_match.group(1))
            all_items = []

            for i in dict_['itemListElement']:
                data = i['item']
                
                alternate_title = data.get('alternateName', '')
                if isinstance(alternate_title, dict):
                    alternate_title = html.unescape(str(alternate_title.get('text', '')).strip())
                else:
                    alternate_title = html.unescape(str(alternate_title).strip()) if alternate_title else ''

                original_name = data.get('name', '')
                if isinstance(original_name, dict):
                    original_name = html.unescape(str(original_name.get('text', '')).strip())
                else:
                    original_name = html.unescape(str(original_name).strip())

                if content_type == 'series':
                    serie_name = alternate_title if alternate_title else original_name
                    if not serie_name:
                        continue
                else:
                    movie_name = alternate_title if alternate_title else original_name
                    if not movie_name:
                        continue

                url = data['url']
                description = html.unescape(data.get('description', ''))
                image = resize_poster(data.get('image', ''))
                if not image:
                    continue

                imdb_id = 'tt' + re.findall(r'/tt(.*?)/', url)[0]
                
                if content_type == 'series':
                    all_items.append((serie_name, image, url, description, imdb_id, original_name))
                else:
                    all_items.append((movie_name, image, url, description, imdb_id, original_name))

            start = (page - 1) * per_page
            end = start + per_page
            itens = all_items[start:end]

        except Exception:
            pass

        return itens

    def imdb_seasons(self, url):
        itens = []
        try:
            response = requests.get(url, headers=self.headers)
            html_text = response.text
            data = self._extract_next_data(html_text)
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
            response = requests.get(url, headers=self.headers)
            html_text = response.text
            data = self._extract_next_data(html_text)
            if not data:
                return itens

            episodes = data['props']['pageProps']['contentData']['section']['episodes']['items']
            fanart = resize_poster(
                data['props']['pageProps']['contentData']['entityMetadata']
                .get('primaryImage', {})
                .get('url', '')
            )

            for idx, ep in enumerate(episodes, start=1):
                title_obj = ep.get('titleText', f'Episódio {idx}')
                if isinstance(title_obj, dict):
                    episode_name = html.unescape(str(title_obj.get('text', f'Episódio {idx}')).strip())
                else:
                    episode_name = html.unescape(str(title_obj).strip())

                img = resize_poster(ep.get('image', {}).get('url', ''))
                description = html.unescape(ep.get('plot', ''))

                itens.append((str(idx), episode_name, img, fanart, description))

        except Exception:
            pass

        return itens


