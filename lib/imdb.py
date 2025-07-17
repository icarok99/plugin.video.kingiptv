# -*- coding: utf-8 -*-
try:
    from lib.ClientScraper import cfscraper
except ImportError:
    from ClientScraper import cfscraper
try:
    from lib.helper import *
except:
    from helper import *
import re

class IMDBScraper:
    def __init__(self):
        self.base = 'https://www.imdb.com'
        self.headers = {
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8'
        }

    def soup(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        return soup

    def search_series(self, search):
        itens = []
        try:
            query = quote(search)
            url = '{0}/find/?q={1}&s=tt&ttype=tv'.format(self.base, query)
            html = cfscraper.get(url, headers=self.headers).text
            json_ = re.findall(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html, re.DOTALL)[0]
            data = json.loads(json_)
            results = data['props']['pageProps']['titleResults']['results']
            for idx, serie in enumerate(results):
                imdb_id = serie['id']
                page = self.base + '/title/' + imdb_id + '/?ref_=fn_tt_tt_' + str(idx)
                name = serie['titleNameText']
                try:
                    year = serie['titleReleaseText']
                    try:
                        year = year.split('-')[0]
                    except:
                        pass
                except:
                    year = '0'
                img = serie.get('titlePosterImageModel', {}).get('url', '')
                if not img:
                    continue  # Ignora conteúdos sem poster
                name = name.replace('&', '&').replace('&apos;', "'")
                itens.append((name, img, page, year, imdb_id))
        except Exception as e:
            print(f"[IMDB] Erro em search_series: {e}")
        return itens

    def series_250(self, limit=250):
        itens = []
        try:
            url = self.base + '/chart/toptv/?ref_=nv_tvv_250'
            html = cfscraper.get(url, headers=self.headers).text
            json_ = re.findall(r'<script type="application/ld\+json">(.+?)</script>', html, re.DOTALL)[0]
            dict_ = json.loads(json_)
            series = dict_['itemListElement']
            if series:
                count = 0
                for i in series:
                    if count >= limit:
                        break
                    data = i['item']
                    name = data.get('alternateName', data.get('name', ''))
                    tip = data['@type']
                    url = data['url']
                    try:
                        description = data['description']
                    except:
                        description = ''
                    image = data.get('image', '')
                    if not image:
                        continue  # Ignora conteúdos sem poster
                    imdb_id = re.findall(r'/tt(.*?)/', url)[0]
                    imdb_id = 'tt' + imdb_id
                    name = name.replace('&', '&').replace('&apos;', "'")
                    description = description.replace('&', '&').replace('&apos;', "'")
                    itens.append((name, image, url, description, imdb_id))
                    count += 1
        except Exception as e:
            print(f"[IMDB] Erro em series_250: {e}")
        return itens

    def series_popular(self, limit=100):
        itens = []
        try:
            url = self.base + '/chart/tvmeter/?ref_=nv_tvv_mptv'
            html = cfscraper.get(url, headers=self.headers).text
            json_ = re.findall(r'<script type="application/ld\+json">(.+?)</script>', html, re.DOTALL)[0]
            dict_ = json.loads(json_)
            series = dict_['itemListElement']
            if series:
                count = 0
                for i in series:
                    if count >= limit:
                        break
                    data = i['item']
                    name = data.get('alternateName', data.get('name', ''))
                    tip = data['@type']
                    url = data['url']
                    try:
                        description = data['description']
                    except:
                        description = ''
                    image = data.get('image', '')
                    if not image:
                        continue  # Ignora conteúdos sem poster
                    imdb_id = re.findall(r'/tt(.*?)/', url)[0]
                    imdb_id = 'tt' + imdb_id
                    name = name.replace('&', '&').replace('&apos;', "'")
                    description = description.replace('&', '&').replace('&apos;', "'")
                    itens.append((name, image, url, description, imdb_id))
                    count += 1
        except Exception as e:
            print(f"[IMDB] Erro em series_popular: {e}")
        return itens

    def imdb_seasons(self, url):
        itens = []
        try:
            html = cfscraper.get(url, headers=self.headers).text
            json_ = re.findall(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html, re.DOTALL)[0]
            data = json.loads(json_)
            seasons = data['props']['pageProps']['mainColumnData']['episodes']['seasons']
            imdb_id = re.findall(r'/tt(.*?)/', url)[0]
            imdb_id = 'tt' + imdb_id
            season_base_url = self.base + '/title/' + imdb_id + '/episodes/?season='
            for idx, season in enumerate(seasons, start=1):
                name = '{0} temporada'.format(str(idx))
                url_season = season_base_url + str(idx)
                itens.append((str(season['number']), name, url_season))
        except Exception as e:
            print(f"[IMDB] Erro em imdb_seasons: {e}")
        return itens

    def imdb_episodes(self, url):
        itens = []
        try:
            html = cfscraper.get(url, headers=self.headers).text
            json_ = re.findall(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html, re.DOTALL)[0]
            data = json.loads(json_)
            episodes = data['props']['pageProps']['contentData']['section']['episodes']['items']
            try:
                fanart = data['props']['pageProps']['contentData']['entityMetadata']['primaryImage']['url']
            except:
                fanart = ''
            if episodes:
                for idx, episode in enumerate(episodes, start=1):
                    episode_number = str(idx)
                    name = episode.get('titleText', 'Episodio - ' + episode_number)
                    img = episode.get('image', {}).get('url', '')
                    if not img:
                        continue  # Ignora conteúdos sem poster
                    description = episode.get('plot', '')
                    name = name.replace('&', '&').replace('&apos;', "'")
                    description = description.replace('&', '&').replace('&apos;', "'")
                    itens.append((episode_number, name, img, fanart, description))
        except Exception as e:
            print(f"[IMDB] Erro em imdb_episodes: {e}")
        return itens

    def search_movies(self, search):
        itens = []
        try:
            query = quote(search)
            url = '{0}/find/?q={1}&s=tt&ttype=ft'.format(self.base, query)
            html = cfscraper.get(url, headers=self.headers).text
            json_ = re.findall(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html, re.DOTALL)[0]
            data = json.loads(json_)
            results = data['props']['pageProps']['titleResults']['results']
            for idx, movie in enumerate(results):
                imdb_id = movie['id']
                page = self.base + '/title/' + imdb_id + '/?ref_=fn_tt_tt_' + str(idx)
                name = movie['titleNameText']
                try:
                    year = movie['titleReleaseText']
                    try:
                        year = year.split('-')[0]
                    except:
                        pass
                except:
                    year = '0'
                img = movie.get('titlePosterImageModel', {}).get('url', '')
                if not img:
                    continue  # Ignora conteúdos sem poster
                name = name.replace('&', '&').replace('&apos;', "'")
                itens.append((name, img, page, year, imdb_id))
        except Exception as e:
            print(f"[IMDB] Erro em search_movies: {e}")
        return itens

    def movies_250(self, limit=250):
        itens = []
        try:
            url = self.base + '/chart/top/?ref_=nv_mv_250'
            html = cfscraper.get(url, headers=self.headers).text
            json_ = re.findall(r'<script type="application/ld\+json">(.+?)</script>', html, re.DOTALL)[0]
            dict_ = json.loads(json_)
            movies = dict_['itemListElement']
            if movies:
                count = 0
                for i in movies:
                    if count >= limit:
                        break
                    data = i['item']
                    name = data.get('alternateName', data.get('name', ''))
                    tip = data['@type']
                    url = data['url']
                    try:
                        description = data['description']
                    except:
                        description = ''
                    image = data.get('image', '')
                    if not image:
                        continue  # Ignora conteúdos sem poster
                    imdb_id = re.findall(r'/tt(.*?)/', url)[0]
                    imdb_id = 'tt' + imdb_id
                    name = name.replace('&', '&').replace('&apos;', "'")
                    description = description.replace('&', '&').replace('&apos;', "'")
                    itens.append((name, image, url, description, imdb_id))
                    count += 1
        except Exception as e:
            print(f"[IMDB] Erro em movies_250: {e}")
        return itens

    def movies_popular(self, limit=100):
        itens = []
        try:
            url = self.base + '/chart/moviemeter/?ref_=nv_mv_mpm'
            html = cfscraper.get(url, headers=self.headers).text
            json_ = re.findall(r'<script type="application/ld\+json">(.+?)</script>', html, re.DOTALL)[0]
            dict_ = json.loads(json_)
            movies = dict_['itemListElement']
            if movies:
                count = 0
                for i in movies:
                    if count >= limit:
                        break
                    data = i['item']
                    name = data.get('alternateName', data.get('name', ''))
                    tip = data['@type']
                    url = data['url']
                    try:
                        description = data['description']
                    except:
                        description = ''
                    image = data.get('image', '')
                    if not image:
                        continue  # Ignora conteúdos sem poster
                    imdb_id = re.findall(r'/tt(.*?)/', url)[0]
                    imdb_id = 'tt' + imdb_id
                    name = name.replace('&', '&').replace('&apos;', "'")
                    description = description.replace('&', '&').replace('&apos;', "'")
                    itens.append((name, image, url, description, imdb_id))
                    count += 1
        except Exception as e:
            print(f"[IMDB] Erro em movies_popular: {e}")
        return itens
