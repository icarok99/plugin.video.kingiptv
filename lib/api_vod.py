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

            if len(options) > 1:
                video_id = options[1]['ID']
            else:
                video_id = options[0]['ID']

            r = requests.post(
                api,
                data={'action': 'getPlayer', 'video_id': video_id},
                headers=h,
                timeout=15
            )

            video_url = r.json().get('data', {}).get('video_url', '').strip()

            if not video_url:
                return ''

            return self._resolve_video_url(video_url, url)

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

            api = f"{self.base}/api"
            h = {
                **headers,
                'origin': self.base,
                'referer': url
            }

            fast_id = next(
                (
                    b.get('data-id')
                    for b in btns
                    if any(x in b.get_text(strip=True).lower() for x in ['fast', 'fast 2', 'fast 3'])
                ),
                None
            )

            video_id = fast_id or btns[0].get('data-id')

            r = requests.post(
                api,
                data={'action': 'getPlayer', 'video_id': video_id},
                headers=h,
                timeout=15
            )

            video_url = r.json().get('data', {}).get('video_url', '').strip()

            if not video_url:
                return ''

            return self._resolve_video_url(video_url, url)

        except Exception:
            return ''

    def _resolve_video_url(self, video_url, referer_url):
        video_url = video_url.strip()

        if re.search(r'\.(mp4|m3u8|ts|mpegurl)(\?|#|$)', video_url, re.I):
            if any(d in video_url.lower() for d in [
                "cnvsplus.com",
                "streamcnvs.com",
                "cdn",
                "watchingvs.com"
            ]):
                return (
                    f"{video_url}"
                    f"|User-Agent={quote_plus(headers['User-Agent'])}"
                    f"&Referer={quote_plus(self.base)}"
                    f"&Origin={quote_plus(self.base)}"
                )

        if "streamcnvs.com" in video_url:
            return f"{video_url}|User-Agent={quote_plus(headers['User-Agent'])}"

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
