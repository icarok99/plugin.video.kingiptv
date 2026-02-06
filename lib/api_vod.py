# -*- coding: utf-8 -*-
try:
    from lib.helper import *
except:
    from helper import *

import re
import json
import requests
from urllib.parse import urlparse, urlencode, quote_plus

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0'
}


class VOD:
    def __init__(self):
        original_base = 'https://superflixapi.cv'
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

    def movie(self, imdb):
        stream = ''
        try:
            url = f'{self.base}/filme/{imdb}'
            r_ = urlparse(url)._replace(path='', query='', fragment='').geturl() + '/'

            headers_ = headers.copy()
            headers_.update({'sec-fetch-dest': 'iframe'})

            r = requests.get(url, headers=headers_)
            html = r.text

            csrf_match = re.search(r'(?:var|let|const)\s+CSRF_TOKEN\s*=\s*[\'"]([^\'"]+)', html)
            csrf = csrf_match.group(1) if csrf_match else ''

            page_match = re.search(r'(?:var|let|const)\s+PAGE_TOKEN\s*=\s*[\'"]([^\'"]+)', html)
            page_token = page_match.group(1) if page_match else ''

            content_match = re.search(r'(?:var|let|const)\s+INITIAL_CONTENT_ID\s*=\s*(\d+)', html)
            if not content_match:
                return ''

            contentid = content_match.group(1)

            headers_.pop('sec-fetch-dest', None)
            headers_.update({
                'origin': self.base,
                'referer': url,
                'x-requested-with': 'XMLHttpRequest',
                'X-Page-Token': page_token
            })

            r = requests.post(
                f'{self.base}/player/options',
                data={
                    'contentid': contentid,
                    'type': 'filme',
                    '_token': csrf,
                    'page_token': page_token,
                    'pageToken': page_token
                },
                headers=headers_
            )

            options = r.json().get('data', {}).get('options', [])
            if not options:
                return ''

            video_id = options[0]['ID']

            r = requests.post(
                f'{self.base}/player/source',
                data={
                    'video_id': video_id,
                    '_token': csrf,
                    'page_token': page_token
                },
                headers=headers_
            )

            video_url = r.json()['data']['video_url']

            r_redirect = requests.get(
                video_url,
                headers={'User-Agent': headers['User-Agent'], 'sec-fetch-dest': 'iframe'},
                allow_redirects=True
            )

            final_video_page = r_redirect.url

            video_hash = final_video_page.strip('/').split('/')[-1]

            parsed = urlparse(final_video_page)
            origin = f'{parsed.scheme}://{parsed.netloc}'
            player = f'{origin}/player/index.php?data={video_hash}&do=getVideo'

            cookies = r_redirect.cookies.get_dict()
            cookie_str = urlencode(cookies)

            r = requests.post(
                player,
                headers={
                    'Origin': origin,
                    'x-requested-with': 'XMLHttpRequest'
                },
                data={'hash': video_hash, 'r': r_},
                cookies=cookies
            )

            src = r.json()
            stream = src['videoSource'] + '|User-Agent=' + quote_plus(headers['User-Agent']) + '&Cookie=' + quote_plus(cookie_str)

        except:
            pass

        return stream

    def tvshows(self, imdb, season, episode):
        stream = ''
        try:
            url = f'{self.base}/serie/{imdb}/{season}/{episode}'
            r_ = urlparse(url)._replace(path='', query='', fragment='').geturl() + '/'

            headers_ = headers.copy()
            headers_.update({'sec-fetch-dest': 'iframe'})

            r = requests.get(url, headers=headers_)
            html = r.text

            m = re.search(r'(?:var|let|const)\s+ALL_EPISODES\s*=\s*({.*?});', html, re.DOTALL)
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

            csrf_match = re.search(r'(?:var|let|const)\s+CSRF_TOKEN\s*=\s*[\'"]([^\'"]+)', html)
            csrf = csrf_match.group(1) if csrf_match else ''

            page_match = re.search(r'(?:var|let|const)\s+PAGE_TOKEN\s*=\s*[\'"]([^\'"]+)', html)
            page_token = page_match.group(1) if page_match else ''

            headers_.pop('sec-fetch-dest', None)
            headers_.update({
                'origin': self.base,
                'referer': url,
                'x-requested-with': 'XMLHttpRequest',
                'X-Page-Token': page_token
            })

            r = requests.post(
                f'{self.base}/player/options',
                data={
                    'contentid': contentid,
                    'type': 'serie',
                    '_token': csrf,
                    'page_token': page_token,
                    'pageToken': page_token
                },
                headers=headers_
            )

            options = r.json().get('data', {}).get('options', [])
            if not options:
                return ''

            video_id = options[0]['ID']

            r = requests.post(
                f'{self.base}/player/source',
                data={
                    'video_id': video_id,
                    '_token': csrf,
                    'page_token': page_token
                },
                headers=headers_
            )

            video_url = r.json()['data']['video_url']

            r_redirect = requests.get(
                video_url,
                headers={'User-Agent': headers['User-Agent'], 'sec-fetch-dest': 'iframe'},
                allow_redirects=True
            )

            final_video_page = r_redirect.url

            video_hash = final_video_page.strip('/').split('/')[-1]

            parsed = urlparse(final_video_page)
            origin = f'{parsed.scheme}://{parsed.netloc}'
            player = f'{origin}/player/index.php?data={video_hash}&do=getVideo'

            cookies = r_redirect.cookies.get_dict()
            cookie_str = urlencode(cookies)

            r = requests.post(
                player,
                headers={
                    'Origin': origin,
                    'x-requested-with': 'XMLHttpRequest'
                },
                data={'hash': video_hash, 'r': r_},
                cookies=cookies
            )

            src = r.json()
            stream = src['videoSource'] + '|User-Agent=' + quote_plus(headers['User-Agent']) + '&Cookie=' + quote_plus(cookie_str)

        except:
            pass

        return stream
