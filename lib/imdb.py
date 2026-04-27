# -*- coding: utf-8 -*-

import re
import json
import html
from urllib.parse import quote

from bs4 import BeautifulSoup

from waf.solver import solve

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'


def resize_poster(url, size='V1_QL100_UX1080'):
    if not url:
        return ''
    return re.sub(r'V1.*?(\.jpg)', size + r'\1', url)


class IMDBScraper:
    def __init__(self, proxy: str = None):
        self.base = 'https://www.imdb.com'
        self.proxy = proxy
        self.headers = {
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'User-Agent': UA,
        }
        self.session = None
        self.token = None
        self._init_waf()

    def _init_waf(self):
        try:
            result, self.session = solve(self.base, UA, proxy=self.proxy)
            self.token = result.get('token', '')
            if self.token:
                self.session.cookies.set('aws-waf-token', self.token, domain='www.imdb.com')
        except Exception:
            import requests as _req
            self.session = _req.Session()
            if self.proxy:
                self.session.proxies = {'http': self.proxy, 'https': self.proxy}

    def _get(self, url: str) -> str:
        resp = self.session.get(url, headers=self.headers)
        if resp.status_code in (403, 429):
            self._init_waf()
            resp = self.session.get(url, headers=self.headers)
        return resp.text

    def soup(self, html_text):
        return BeautifulSoup(html_text, 'html.parser')

    def _extract_next_data(self, html_text):
        match = re.search(
            r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
            html_text, re.DOTALL
        )
        if not match:
            return None
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

    def _parse_search_results(self, html_text, name_key: str):
        itens = []
        data = self._extract_next_data(html_text)
        if not data:
            return itens
        results = (
            data.get('props', {}).get('pageProps', {})
            .get('searchResults', {}).get('titleResults', {})
            .get('titleListItems', [])
        )
        for item in results:
            imdb_id = item.get('titleId', '')
            if not imdb_id.startswith('tt'):
                continue
            title = html.unescape(str(item.get('titleText', '')).strip())
            orig_title = html.unescape(str(item.get('originalTitleText', '')).strip())
            if not title:
                title = orig_title
            year = str(item.get('releaseYear', 0) or 0)
            img = resize_poster(item.get('primaryImage', {}).get('url', ''))
            description = html.unescape(str(item.get('plot', '')).strip())
            if not img or not title:
                continue
            page = f'{self.base}/title/{imdb_id}/'
            itens.append((title, img, page, description, imdb_id, orig_title, year))
        return itens

    def search_series(self, search):
        itens = []
        try:
            url = f'{self.base}/pt/search/title/?title={quote(search)}&title_type=tv_series'
            itens = self._parse_search_results(self._get(url), 'titleText')
        except Exception:
            pass
        return itens

    def search_movies(self, search):
        itens = []
        try:
            url = f'{self.base}/pt/search/title/?title={quote(search)}&title_type=feature'
            itens = self._parse_search_results(self._get(url), 'titleText')
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
            html_text = self._get(self.base + chart_path)

            year_map = {}
            try:
                next_data = self._extract_next_data(html_text)
                if next_data:
                    edges = (
                        next_data.get('props', {}).get('pageProps', {})
                        .get('pageData', {}).get('chartTitles', {}).get('edges', [])
                    )
                    for edge in edges:
                        node = edge.get('node', {})
                        nid = node.get('id', '')
                        year_val = node.get('releaseYear', {})
                        if isinstance(year_val, dict):
                            year_val = str(year_val.get('year', '') or '')
                        else:
                            year_val = str(year_val or '')
                        if nid and year_val and year_val != '0':
                            year_map[nid] = year_val
            except Exception:
                pass

            json_match = re.search(
                r'<script type="application/ld\+json">(.+?)</script>',
                html_text, re.DOTALL
            )
            if not json_match:
                return itens

            dict_ = json.loads(json_match.group(1))
            all_items = []

            for i in dict_['itemListElement']:
                data = i['item']

                alt_title = data.get('alternateName', '')
                alt_title = html.unescape(
                    str(alt_title.get('text', '') if isinstance(alt_title, dict) else alt_title).strip()
                )
                orig_name = data.get('name', '')
                orig_name = html.unescape(
                    str(orig_name.get('text', '') if isinstance(orig_name, dict) else orig_name).strip()
                )

                display_name = alt_title if alt_title else orig_name
                if not display_name:
                    continue

                item_url = data['url']
                description = html.unescape(data.get('description', ''))
                image = resize_poster(data.get('image', ''))
                if not image:
                    continue

                imdb_id = 'tt' + re.findall(r'/tt(.*?)/', item_url)[0]
                year = year_map.get(imdb_id, '')
                all_items.append((display_name, image, item_url, description, imdb_id, orig_name, year))

            start = (page - 1) * per_page
            itens = all_items[start:start + per_page]

        except Exception:
            pass
        return itens

    def imdb_seasons(self, url):
        itens = []
        try:
            data = self._extract_next_data(self._get(url))
            if not data:
                return itens
            seasons = data['props']['pageProps']['mainColumnData']['episodes']['seasons']
            imdb_id = 'tt' + re.findall(r'/tt(.*?)/', url)[0]
            base_url = f'{self.base}/title/{imdb_id}/episodes/?season='
            for season in seasons:
                num = str(season['number'])
                name = f'{num} temporada'
                itens.append((num, name, base_url + num))
        except Exception:
            pass
        return itens

    def imdb_episodes(self, url):
        itens = []
        try:
            data = self._extract_next_data(self._get(url))
            if not data:
                return itens
            episodes = data['props']['pageProps']['contentData']['section']['episodes']['items']
            fanart = resize_poster(
                data['props']['pageProps']['contentData']['entityMetadata']
                .get('primaryImage', {}).get('url', '')
            )
            for idx, ep in enumerate(episodes, start=1):
                title_obj = ep.get('titleText', f'Episódio {idx}')
                episode_name = html.unescape(
                    str(title_obj.get('text', f'Episódio {idx}') if isinstance(title_obj, dict) else title_obj).strip()
                )
                img = resize_poster(ep.get('image', {}).get('url', ''))
                description = html.unescape(ep.get('plot', ''))
                itens.append((str(idx), episode_name, img, fanart, description))
        except Exception:
            pass
        return itens
