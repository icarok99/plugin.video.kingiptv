# -*- coding: utf-8 -*-
try:
    from lib.ClientScraper import cfscraper, USER_AGENT
except ImportError:
    from ClientScraper import cfscraper, USER_AGENT
try:
    from lib.helper import *
except:
    from helper import *
import re
from urllib.parse import urlparse, urlencode, quote_plus
from bs4 import BeautifulSoup
import time

# -------------------
# API VOD - versão reforçada de tentativas (Referer + headers + logs)
# -------------------
class VOD:
    def __init__(self):
        self.base = '\x68\x74\x74\x70\x73\x3a\x2f\x2f\x73\x75\x70\x65\x72\x66\x6c\x69\x78\x61\x70\x69\x2e\x64\x69\x67\x69\x74\x61\x6c'
        # lista de possíveis "parent referers" a tentar (ordem: mais provável primeiro)
        self.parent_candidates = [
            "https://iframetester.com/",
            "https://iframetester.com",
            "https://iframetester.com/embed",
        ]
        # headers base para simular navegador
        self.base_headers = {
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            # 'Sec-Fetch-*' aproximados para imitar iframe cross-site
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Dest': 'iframe',
        }

    def _debug_trim(self, text, n=500):
        if not text:
            return ''
        return text[:n].replace('\n', ' ').replace('\r', ' ')

    def _fetch_player_video_source(self, session, video_url, r_):
        """
        Dado o video_url (retornado pela API), faz o fluxo final para extrair videoSource.
        Retorna stream string já formatada (ou '' em falha).
        """
        try:
            video_hash = video_url.split('/')[-1]
            parsed_url = urlparse(video_url)
            origin = '{uri.scheme}://{uri.netloc}'.format(uri=parsed_url)
            player = '{uri.scheme}://{uri.netloc}/player/index.php?data={0}&do=getVideo'.format(video_hash, uri=parsed_url)

            # GET no video_url para pegar cookies necessários
            r = session.get(video_url, headers={**self.base_headers, 'Referer': self.base + '/'}, allow_redirects=True, timeout=20)
            print(f"[player] GET {video_url} -> {r.status_code}")
            cookies_dict = r.cookies.get_dict()
            cookie_string = urlencode(cookies_dict)

            # POST para o endpoint do player
            headers_post = {
                'Origin': origin,
                'x-requested-with': 'XMLHttpRequest',
                'Referer': r_.rstrip('/'),
                'User-Agent': USER_AGENT,
            }
            r = session.post(player, headers=headers_post, data={'hash': str(video_hash), 'r': r_}, cookies=cookies_dict, timeout=20)
            print(f"[player] POST {player} -> {r.status_code}")
            src = r.json() if r.status_code == 200 else {}
            videoSource = src.get('videoSource') if isinstance(src, dict) else None
            if not videoSource:
                print(f"[player] resposta inesperada: {self._debug_trim(r.text)}")
                return ''
            return videoSource + '|User-Agent=' + quote_plus(USER_AGENT) + '&Cookie=' + quote_plus(cookie_string)
        except Exception as e:
            print(f"[player] Erro ao buscar videoSource: {e}")
            return ''

    def tvshows(self, imdb, season, episode):
        stream = ''
        try:
            if not (imdb and season and episode):
                return ''

            # cria/usa session do cfscraper para persistir cookies / bypass CF
            session = cfscraper

            # 1) acessa homepage do site para pegar cookies iniciais
            try:
                r_home = session.get(self.base, headers=self.base_headers, timeout=20)
                print(f"[tvshows] GET homepage {self.base} -> {r_home.status_code}")
            except Exception as e:
                print(f"[tvshows] aviso: falha ao GET homepage: {e}")

            # montar url do episódio
            url = '{0}/serie/{1}/{2}/{3}'.format(self.base, imdb, season, episode)
            parsed_url_r = urlparse(url)
            r_ = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_url_r)

            # 2) tentar diversos referers de "pai"
            last_page_src = ''
            found = False
            for parent in self.parent_candidates:
                try:
                    headers = {**self.base_headers, 'Referer': parent, 'User-Agent': USER_AGENT}
                    r = session.get(url, headers=headers, allow_redirects=True, timeout=20)
                    print(f"[tvshows] GET {url} com Referer={parent} -> {r.status_code}")
                    src = r.text
                    last_page_src = src
                    soup = BeautifulSoup(src, 'html.parser')

                    # busca o elemento do episodio (duas possíveis variações)
                    div = None
                    try:
                        div = soup.find('episode-item', class_='episodeOption active')
                    except:
                        div = None
                    if not div:
                        try:
                            div = soup.find('div', class_='episodeOption active')
                        except:
                            div = None

                    if div:
                        found = True
                        print("[tvshows] encontrou bloco do episódio.")
                        break
                    else:
                        print("[tvshows] bloco do episódio NÃO encontrado com esse Referer; tentando próximo.")
                except Exception as e:
                    print(f"[tvshows] erro ao GET com Referer {parent}: {e}")
                    continue

            if not found:
                print("[tvshows] Não foi possível obter o HTML do episódio. Trecho da página:")
                print(self._debug_trim(last_page_src))
                return ''

            data_contentid = div.get('data-contentid') if div else None
            if not data_contentid:
                print("[tvshows] data-contentid não encontrado no bloco do episódio.")
                return ''

            api = '{0}/api'.format(self.base)
            r = session.post(api, headers={**self.base_headers, 'Referer': self.base + '/'}, data={'action': 'getOptions', 'contentid': data_contentid}, timeout=20)
            print(f"[tvshows] POST getOptions -> {r.status_code}")
            src = r.json() if r.status_code == 200 else {}
            id_ = None
            try:
                id_ = src['data']['options'][0]['ID']
            except Exception as e:
                print(f"[tvshows] falha ao extrair ID em getOptions: {e}; resposta: {src}")
                return ''

            # getPlayer para obter video_url
            r = session.post(api, headers={**self.base_headers, 'Referer': self.base + '/'}, data={'action': 'getPlayer', 'video_id': id_}, timeout=20)
            print(f"[tvshows] POST getPlayer -> {r.status_code}")
            src = r.json() if r.status_code == 200 else {}
            video_url = src.get('data', {}).get('video_url') if isinstance(src, dict) else None
            if not video_url:
                print(f"[tvshows] video_url não encontrado em getPlayer. Resposta: {src}")
                return ''

            # fluxo final para extrair videoSource
            stream = self._fetch_player_video_source(session, video_url, r_)
        except Exception as e:
            print(f"[tvshows] Erro geral: {e}")
        return stream

    def movie(self, imdb):
        stream = ''
        try:
            if not imdb:
                return ''

            session = cfscraper

            # 1) homepage para cookie inicial
            try:
                r_home = session.get(self.base, headers=self.base_headers, timeout=20)
                print(f"[movie] GET homepage {self.base} -> {r_home.status_code}")
            except Exception as e:
                print(f"[movie] aviso: falha ao GET homepage: {e}")

            url = '{0}/filme/{1}'.format(self.base, imdb)
            parsed_url_r = urlparse(url)
            r_ = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_url_r)

            last_page_src = ''
            found = False
            # tenta varios referers
            for parent in self.parent_candidates:
                try:
                    headers = {**self.base_headers, 'Referer': parent, 'User-Agent': USER_AGENT}
                    r = session.get(url, headers=headers, allow_redirects=True, timeout=20)
                    print(f"[movie] GET {url} com Referer={parent} -> {r.status_code}")
                    src = r.text
                    last_page_src = src
                    soup = BeautifulSoup(src, 'html.parser')

                    div = soup.find('div', {'class': 'players_select'})
                    if div:
                        found = True
                        print("[movie] encontrou bloco players_select.")
                        break
                    else:
                        print("[movie] players_select não encontrado com esse Referer; tentando próximo.")
                except Exception as e:
                    print(f"[movie] erro ao GET com Referer {parent}: {e}")
                    continue

            if not found:
                print("[movie] Não foi possível obter o HTML do filme. Trecho da página:")
                print(self._debug_trim(last_page_src))
                return ''

            # extrair data-id do player
            try:
                player_item = div.find('div', {'class': 'player_select_item'})
                data_id = player_item.get('data-id', '') if player_item else ''
            except Exception as e:
                print(f"[movie] erro ao extrair data-id: {e}")
                data_id = ''

            if not data_id:
                print("[movie] data-id não encontrado no bloco players_select.")
                return ''

            api = '{0}/api'.format(self.base)
            r = session.post(api, headers={**self.base_headers, 'Referer': self.base + '/'}, data={'action': 'getPlayer', 'video_id': data_id}, timeout=20)
            print(f"[movie] POST getPlayer -> {r.status_code}")
            src = r.json() if r.status_code == 200 else {}
            video_url = src.get('data', {}).get('video_url') if isinstance(src, dict) else None
            if not video_url:
                print(f"[movie] video_url não encontrado em getPlayer. Resposta: {src}")
                return ''

            stream = self._fetch_player_video_source(session, video_url, r_)
        except Exception as e:
            print(f"[movie] Erro geral: {e}")
        return stream
