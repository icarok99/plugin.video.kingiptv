# -*- coding: utf-8 -*-
import re
import json
import requests
from urllib.parse import urlparse, urlencode, quote_plus
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0'
}

class VOD:
    def __init__(self):
        original_base = 'https://superflixapi.asia'
        self.base = self.get_last_base(original_base)

    def get_last_base(self, url):
        last_url = url
        try:
            r = requests.get(url, headers=headers, timeout=4)
            last_url = r.url
        except Exception:
            pass

        if last_url and last_url.endswith('/'):
            last_url = last_url[:-1]
        return last_url

    def tvshows(self, imdb, season, episode):
        try:
            url = f'{self.base}/serie/{imdb}/{season}/{episode}'

            r = requests.get(
                url,
                headers={**headers, 'sec-fetch-dest': 'iframe'},
                timeout=15
            )

            match = re.search(r'var ALL_EPISODES\s*=\s*({.*?});', r.text, re.DOTALL)
            if not match:
                return ''

            episodes = json.loads(match.group(1))
            contentid = next(
                (
                    ep['ID']
                    for ep in episodes.get(str(season), [])
                    if str(ep.get('epi_num')) == str(episode)
                ),
                None
            )

            if not contentid:
                return ''

            api = f"{self.base}/api"
            h = {
                **headers,
                'origin': self.base,
                'referer': url
            }

            r = requests.post(
                api,
                data={'action': 'getOptions', 'contentid': contentid},
                headers=h,
                timeout=15
            )

            options = r.json().get('data', {}).get('options', [])
            if not options:
                return ''

            def server_priority(opt):
                name = opt.get('name', '').lower()
                if 'fast' in name:
                    return 0
                if 'premium' in name:
                    return 1
                return 2

            options.sort(key=server_priority)

            for opt in options:
                video_id = opt.get('ID')
                if not video_id:
                    continue

                r = requests.post(
                    api,
                    data={'action': 'getPlayer', 'video_id': video_id},
                    headers=h,
                    timeout=15
                )

                video_url = r.json().get('data', {}).get('video_url', '').strip()
                if not video_url:
                    continue

                resolved = self._resolve_video_url(video_url, url)
                if resolved:
                    return resolved

            return ''

        except Exception:
            return ''

    def movie(self, imdb):
        try:
            url = f'{self.base}/filme/{imdb}'

            r = requests.get(
                url,
                headers={**headers, 'sec-fetch-dest': 'iframe'},
                timeout=15
            )

            soup = BeautifulSoup(r.text, "html.parser")
            btns = soup.find_all("div", class_="btn-server")
            if not btns:
                return ''

            fast = []
            premium = []
            others = []

            for b in btns:
                t = b.get_text(strip=True).lower()
                if 'fast' in t:
                    fast.append(b)
                elif 'premium' in t:
                    premium.append(b)
                else:
                    others.append(b)

            btns = fast + premium + others

            api = f"{self.base}/api"
            h = {
                **headers,
                'origin': self.base,
                'referer': url
            }

            for b in btns:
                video_id = b.get('data-id')
                if not video_id:
                    continue

                r = requests.post(
                    api,
                    data={'action': 'getPlayer', 'video_id': video_id},
                    headers=h,
                    timeout=15
                )

                video_url = r.json().get('data', {}).get('video_url', '').strip()
                if not video_url:
                    continue

                resolved = self._resolve_video_url(video_url, url)
                if resolved:
                    return resolved

            return ''

        except Exception:
            return ''

    def _strip_subtitle(self, video_url):
        if '?s=' in video_url:
            video_url = video_url.split('?s=', 1)[0]
        return video_url.strip()

    def _resolve_video_url(self, video_url, referer_url):
        video_url = self._strip_subtitle(video_url)

        if re.search(r'\.(mp4|m3u8|ts|mpegurl)(\?|#|$)', video_url, re.I):
            return (
                f"{video_url}"
                f"|User-Agent={quote_plus(headers['User-Agent'])}"
                f"&Referer={quote_plus(self.base)}"
                f"&Origin={quote_plus(self.base)}"
            )

        try:
            video_hash = video_url.strip("/").split("/")[-1]
            parsed = urlparse(video_url)
            origin = f"{parsed.scheme}://{parsed.netloc}"
            player = f"{origin}/player/index.php?data={video_hash}&do=getVideo"

            r = requests.get(
                video_url,
                headers={**headers, 'sec-fetch-dest': 'iframe'},
                timeout=15
            )

            cookies = r.cookies.get_dict()

            r = requests.post(
                player,
                headers={
                    'Origin': origin,
                    'Referer': video_url,
                    'X-Requested-With': 'XMLHttpRequest',
                    'User-Agent': headers['User-Agent']
                },
                data={'hash': video_hash, 'r': referer_url},
                cookies=cookies,
                timeout=15
            )

            js = r.json()
            if js.get("videoSource"):
                return (
                    f"{js['videoSource']}"
                    f"|User-Agent={quote_plus(headers['User-Agent'])}"
                    f"&Cookie={quote_plus(urlencode(cookies))}"
                    f"&Referer={quote_plus(origin)}"
                )

        except Exception:
            pass

        return ''
