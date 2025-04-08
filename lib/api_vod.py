import urllib.request
from urllib.parse import urlparse, quote_plus
from bs4 import BeautifulSoup

try:
    from lib.ClientScraper import cfscraper, USER_AGENT
except ImportError:
    from ClientScraper import cfscraper, USER_AGENT
try:
    from lib.helper import *
except:
    from helper import *

class VOD:
    def __init__(self):
        # URL padrão (fallback)
        self.base = 'https://superflixapi.cx'
        
        # Tenta buscar a URL da API remotamente via Pastebin
        self._update_base_from_pastebin()

    def _update_base_from_pastebin(self):
        """
        Atualiza a URL base (self.base) a partir de um Pastebin remoto.
        Se a requisição falhar, mantém a URL padrão.
        """
        pastebin_url = 'https://pastebin.com/raw/swVZFujg'  # Substitua pelo seu link do Pastebin
        try:
            # Faz a requisição usando urllib
            with urllib.request.urlopen(pastebin_url, timeout=5) as response:
                new_base = response.read().decode('utf-8').strip()  # Lê o conteúdo e remove espaços em branco
                if new_base:
                    self.base = new_base  # Atualiza a URL base
                    print(f"URL base atualizada remotamente: {self.base}")
                else:
                    print("Pastebin vazio. Mantendo URL padrão.")
        except Exception as e:
            print(f"Erro ao buscar URL do Pastebin: {e}. Mantendo URL padrão: {self.base}")

    def tvshows(self, imdb, season, episode):
        stream = ''
        try:
            if imdb and season and episode:
                url = '{0}/serie/{1}/{2}/{3}'.format(self.base, imdb, season, episode)
                parsed_url_r = urlparse(url)
                r_ = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_url_r)
                r = cfscraper.get(url)
                src = r.text
                soup = BeautifulSoup(src, 'html.parser')
                try:
                    div = soup.find('episode-item', class_='episodeOption active')
                except:
                    div = {}
                if not div:
                    try:
                        div = soup.find('div', class_='episodeOption active')
                    except:
                        div = {}
                data_contentid = div['data-contentid']
                api = '{0}/api'.format(self.base)
                r = cfscraper.post(api, data={'action': 'getOptions', 'contentid': data_contentid})
                src = r.json()
                id_ = src['data']['options'][0]['ID']
                r = cfscraper.post(api, data={'action': 'getPlayer', 'video_id': id_})
                src = r.json()
                video_url = src['data']['video_url']
                video_hash = video_url.split('/')[-1]
                parsed_url = urlparse(video_url)
                origin = '{uri.scheme}://{uri.netloc}'.format(uri=parsed_url)
                player = '{uri.scheme}://{uri.netloc}/player/index.php?data={0}&do=getVideo'.format(video_hash, uri=parsed_url)
                r = cfscraper.get(video_url, headers={'Referer': self.base + '/'})
                cookies_dict = r.cookies.get_dict()
                r = cfscraper.post(player, headers={'Origin': origin, 'x-requested-with': 'XMLHttpRequest'}, data={'hash': str(video_hash), 'r': r_}, cookies=cookies_dict)
                src = r.json()
                stream = src['videoSource'] + '|User-Agent=' + quote_plus(USER_AGENT) + '&Cookie=' + quote_plus('fireplayer_player=biinhfqat31jg8ripa3uvurum4')
        except:
            pass
        return stream

    def movie(self, imdb):
        stream = ''
        try:
            if imdb:
                url = '{0}/filme/{1}'.format(self.base, imdb)
                parsed_url_r = urlparse(url)
                r_ = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_url_r)
                r = cfscraper.get(url)
                src = r.text
                soup = BeautifulSoup(src, 'html.parser')
                div = soup.find('div', {'class': 'players_select'})  # dublado
                data_id = div.find('div', {'class': 'player_select_item'}).get('data-id', '')
                api = '{0}/api'.format(self.base)
                r = cfscraper.post(api, data={'action': 'getPlayer', 'video_id': data_id})
                src = r.json()
                video_url = src['data']['video_url']
                video_hash = video_url.split('/')[-1]
                parsed_url = urlparse(video_url)
                origin = '{uri.scheme}://{uri.netloc}'.format(uri=parsed_url)
                player = '{uri.scheme}://{uri.netloc}/player/index.php?data={0}&do=getVideo'.format(video_hash, uri=parsed_url)
                r = cfscraper.get(video_url, headers={'Referer': self.base + '/'})
                cookies_dict = r.cookies.get_dict()
                r = cfscraper.post(player, headers={'Origin': origin, 'x-requested-with': 'XMLHttpRequest'}, data={'hash': str(video_hash), 'r': r_}, cookies=cookies_dict)
                src = r.json()
                stream = src['videoSource'] + '|User-Agent=' + quote_plus(USER_AGENT) + '&Cookie=' + quote_plus('fireplayer_player=biinhfqat31jg8ripa3uvurum4')
        except:
            pass
        return stream

# Exemplo de uso
# print(VOD().movie('tt0106697'))
# print(VOD().tvshows('tt3107288', '1', '1'))
