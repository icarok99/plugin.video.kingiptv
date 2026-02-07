# -*- coding: utf-8 -*-
try:
    from lib.helper import *
except:
    from helper import *
import re
import json
import requests
from urllib.parse import urlparse, urlencode, quote_plus
from bs4 import BeautifulSoup

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0'}

class VOD:
    def __init__(self):
        original_base = 'https://superflixapi.asia'
        self.base = self.get_last_base(original_base)

    def get_last_base(self, url):
        last_url = url
        try:
            r = requests.get(url, headers=headers, timeout=4)
            last_url = r.url
        except:
            pass
        if last_url and last_url.endswith('/'):
            last_url = last_url[:-1]
        return last_url

    def tvshows(self, imdb, season, episode):
        stream = ''
        try:
            url = f'{self.base}/serie/{imdb}/{season}/{episode}'
            r_ = urlparse(url)._replace(path='', query='', fragment='').geturl() + '/'
            headers_ = headers.copy()
            headers_.update({'sec-fetch-dest': 'iframe'})

            r = requests.get(url, headers=headers_)
            html = r.text

            m = re.search(r'var ALL_EPISODES\s*=\s*({.*?});', html, re.DOTALL)
            if not m:
                return ''
            all_episodes = json.loads(m.group(1))

            episodes = all_episodes.get(str(season), [])
            contentid = None
            for ep in episodes:
                if str(ep.get('epi_num')) == str(episode):
                    contentid = ep['ID']
                    break
            if not contentid:
                return ''

            api = f'{self.base}/api'
            headers_.pop('sec-fetch-dest', None)
            headers_.update({'origin': self.base, 'referer': url})

            r = requests.post(api, data={'action': 'getOptions', 'contentid': contentid}, headers=headers_)
            options = r.json().get('data', {}).get('options', [])
            if not options:
                return ''
            video_id = options[0]['ID']

            r = requests.post(api, data={'action': 'getPlayer', 'video_id': video_id}, headers=headers_)
            video_url = r.json()['data']['video_url']
            video_hash = video_url.strip('/').split('/')[-1]

            parsed = urlparse(video_url)
            origin = f'{parsed.scheme}://{parsed.netloc}'
            player = f'{origin}/player/index.php?data={video_hash}&do=getVideo'

            r = requests.get(video_url, headers={'User-Agent': headers['User-Agent'], 'sec-fetch-dest': 'iframe'})
            cookies = r.cookies.get_dict()
            cookie_str = urlencode(cookies)

            r = requests.post(player,
                              headers={'Origin': origin, 'x-requested-with': 'XMLHttpRequest'},
                              data={'hash': video_hash, 'r': r_},
                              cookies=cookies)
            src = r.json()
            stream = src['videoSource'] + '|User-Agent=' + quote_plus(headers['User-Agent']) + '&Cookie=' + quote_plus(cookie_str)
        except:
            pass
        return stream

    def movie(self, imdb):
        stream = ''
        try:
            url = f'{self.base}/filme/{imdb}'
            r_ = urlparse(url)._replace(path='', query='', fragment='').geturl() + '/'
            headers_ = headers.copy()
            headers_.update({'sec-fetch-dest': 'iframe'})

            r = requests.get(url, headers=headers_)
            soup = BeautifulSoup(r.text, 'html.parser')
            btn = soup.find('div', class_='btn-server')
            data_id = btn['data-id']

            api = f'{self.base}/api'
            headers_.pop('sec-fetch-dest', None)
            headers_.update({'origin': self.base, 'referer': url})

            r = requests.post(api, data={'action': 'getPlayer', 'video_id': data_id}, headers=headers_)
            video_url = r.json()['data']['video_url']
            video_hash = video_url.strip('/').split('/')[-1]

            parsed = urlparse(video_url)
            origin = f'{parsed.scheme}://{parsed.netloc}'
            player = f'{origin}/player/index.php?data={video_hash}&do=getVideo'

            r = requests.get(video_url, headers={'User-Agent': headers['User-Agent'], 'sec-fetch-dest': 'iframe'})
            cookies = r.cookies.get_dict()
            cookie_str = urlencode(cookies)

            r = requests.post(player,
                              headers={'Origin': origin, 'x-requested-with': 'XMLHttpRequest'},
                              data={'hash': video_hash, 'r': r_},
                              cookies=cookies)
            src = r.json()
            stream = src['videoSource'] + '|User-Agent=' + quote_plus(headers['User-Agent']) + '&Cookie=' + quote_plus(cookie_str)
        except:
            pass
        return stream
