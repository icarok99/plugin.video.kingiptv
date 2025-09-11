# -*- coding: utf-8 -*-
# try:
#     from lib.ClientScraper import cfscraper, USER_AGENT
# except ImportError:
#     from ClientScraper import cfscraper, USER_AGENT
try:
    from lib.helper import *
except:
    from helper import *
import re
import requests

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0'}

class VOD:
    def __init__(self):
        original_base = 'https://superflixapi.work'
        self.base = self.get_last_base(original_base)
        print(f"Initialized VOD with base URL: {self.base}")

    def get_last_base(self, url):
        last_url = url
        try:
            r = requests.get(url, headers=headers, timeout=4)
            last_url = r.url
        except Exception as e:
            print(f"get_last_base error: {e}")

        if last_url and last_url.endswith('/'):
            last_url = last_url[:-1]
        return last_url

    def tvshows(self,imdb,season,episode):
        stream = ''
        try:
            if imdb and season and episode:
                url = '{0}/serie/{1}/{2}/{3}'.format(self.base,imdb,season,episode)
                parsed_url_r = urlparse(url)
                r_ = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_url_r)
                headers_ = headers
                headers_.update({'sec-fetch-dest': 'iframe'})                
                r = requests.get(url, headers=headers_)
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
                headers_.pop('sec-fetch-dest', None)
                headers_.update({'origin': self.base, 'referer': url})
                r = requests.post(api,data={'action': 'getOptions', 'contentid': data_contentid}, headers=headers_)
                src = r.json()
                id_ = src['data']['options'][0]['ID']
                r = requests.post(api,data={'action': 'getPlayer', 'video_id': id_}, headers=headers_)
                src = r.json()
                video_url = src['data']['video_url']
                video_hash = video_url.split('/')[-1]
                parsed_url = urlparse(video_url)
                origin = '{uri.scheme}://{uri.netloc}'.format(uri=parsed_url)
                player = '{uri.scheme}://{uri.netloc}/player/index.php?data={0}&do=getVideo'.format(video_hash, uri=parsed_url)
                r = requests.get(video_url, headers={'User-Agent': headers_['User-Agent'], 'sec-fetch-dest': 'iframe'})
                cookies_dict = r.cookies.get_dict()
                cookie_string = urlencode(cookies_dict)
                r = requests.post(player,headers={'Origin': origin, 'x-requested-with': 'XMLHttpRequest'}, data={'hash': str(video_hash), 'r': r_}, cookies=cookies_dict)
                src = r.json()
                stream = src['videoSource'] + '|User-Agent=' + quote_plus(headers_['User-Agent']) + '&Cookie=' + quote_plus(cookie_string)
        except:
            pass       
        return stream
    
    def movie(self,imdb):
        stream = ''
        try:
            if imdb:
                url = '{0}/filme/{1}'.format(self.base,imdb)
                parsed_url_r = urlparse(url)
                r_ = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_url_r)
                headers_ = headers
                headers_.update({'sec-fetch-dest': 'iframe'})
                r = requests.get(url, headers=headers_)
                src = r.text
                soup = BeautifulSoup(src, 'html.parser')
                div = soup.find('div',{'class': 'players_select'}) # dublado
                data_id = div.find('div', {'class': 'player_select_item'}).get('data-id', '')
                api = '{0}/api'.format(self.base)
                headers_.pop('sec-fetch-dest', None)
                headers_.update({'origin': self.base, 'referer': url})
                r = requests.post(api,data={'action': 'getPlayer', 'video_id': data_id}, headers=headers_)
                src = r.json()
                video_url = src['data']['video_url']
                video_hash = video_url.split('/')[-1]
                parsed_url = urlparse(video_url)
                origin = '{uri.scheme}://{uri.netloc}'.format(uri=parsed_url)
                player = '{uri.scheme}://{uri.netloc}/player/index.php?data={0}&do=getVideo'.format(video_hash, uri=parsed_url)
                r = requests.get(video_url, headers={'User-Agent': headers_['User-Agent'], 'sec-fetch-dest': 'iframe'})
                cookies_dict = r.cookies.get_dict()
                cookie_string = urlencode(cookies_dict)
                r = requests.post(player,headers={'Origin': origin, 'x-requested-with': 'XMLHttpRequest'}, data={'hash': str(video_hash), 'r': r_}, cookies=cookies_dict)
                src = r.json()
                stream = src['videoSource'] + '|User-Agent=' + quote_plus(headers_['User-Agent']) + '&Cookie=' + quote_plus(cookie_string)
        except:
            pass
        return stream

#print(VOD().movie('tt0106697'))
#print(VOD().tvshows('tt3107288','1','1'))
    


