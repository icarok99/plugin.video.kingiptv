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
        self.base = 'https://superflixapi.shop'
        print(f"Initialized VOD with base URL: {self.base}")

    def tvshows(self, imdb, season, episode):
        stream = ''
        try:
            if imdb and season and episode:
                url = '{0}/serie/{1}/{2}/{3}'.format(self.base, imdb, season, episode)
                print(f"Fetching TV show URL: {url}")
                parsed_url_r = urlparse(url)
                r_ = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_url_r)
                headers_ = headers
                headers_.update({'sec-fetch-dest': 'iframe'})                
                r = requests.get(url, headers=headers_)
                print(f"TV show page response status: {r.status_code}")
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
                if not div:
                    print("No active episode option found")
                    return stream
                data_contentid = div['data-contentid']
                print(f"Found data-contentid: {data_contentid}")
                api = '{0}/api'.format(self.base)
                headers_.pop('sec-fetch-dest', None)
                headers_.update({'origin': self.base, 'referer': url})
                r = requests.post(api, data={'action': 'getOptions', 'contentid': data_contentid}, headers=headers_)
                print(f"API getOptions response status: {r.status_code}")
                src = r.json()
                id_ = src['data']['options'][0]['ID']
                print(f"Retrieved video ID: {id_}")
                r = requests.post(api, data={'action': 'getPlayer', 'video_id': id_}, headers=headers_)
                print(f"API getPlayer response status: {r.status_code}")
                src = r.json()
                video_url = src['data']['video_url']
                print(f"Video URL: {video_url}")
                video_hash = video_url.split('/')[-1]
                parsed_url = urlparse(video_url)
                origin = '{uri.scheme}://{uri.netloc}'.format(uri=parsed_url)
                player = '{uri.scheme}://{uri.netloc}/player/index.php?data={0}&do=getVideo'.format(video_hash, uri=parsed_url)
                r = requests.get(video_url, headers={'User-Agent': headers_['User-Agent'], 'sec-fetch-dest': 'iframe'})
                print(f"Video URL response status: {r.status_code}")
                cookies_dict = r.cookies.get_dict()
                cookie_string = urlencode(cookies_dict)
                print(f"Cookies: {cookie_string}")
                r = requests.post(player, headers={'Origin': origin, 'x-requested-with': 'XMLHttpRequest'}, data={'hash': str(video_hash), 'r': r_}, cookies=cookies_dict)
                print(f"Player response status: {r.status_code}")
                src = r.json()
                stream = src['videoSource'] + '|User-Agent=' + quote_plus(headers_['User-Agent']) + '&Cookie=' + quote_plus(cookie_string)
                print(f"Final stream URL: {stream}")
        except Exception as e:
            print(f"Error in tvshows: {str(e)}")
        return stream
    
    def movie(self, imdb):
        stream = ''
        try:
            if imdb:
                url = '{0}/filme/{1}'.format(self.base, imdb)
                print(f"Fetching movie URL: {url}")
                parsed_url_r = urlparse(url)
                r_ = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_url_r)
                headers_ = headers
                headers_.update({'sec-fetch-dest': 'iframe'})
                r = requests.get(url, headers=headers_)
                print(f"Movie page response status: {r.status_code}")
                src = r.text
                soup = BeautifulSoup(src, 'html.parser')
                div = soup.find('div', {'class': 'players_select'})
                if not div:
                    print("No players_select div found")
                    return stream
                data_id = div.find('div', {'class': 'player_select_item'}).get('data-id', '')
                print(f"Found data-id: {data_id}")
                api = '{0}/api'.format(self.base)
                headers_.pop('sec-fetch-dest', None)
                headers_.update({'origin': self.base, 'referer': url})
                r = requests.post(api, data={'action': 'getPlayer', 'video_id': data_id}, headers=headers_)
                print(f"API getPlayer response status: {r.status_code}")
                src = r.json()
                video_url = src['data']['video_url']
                print(f"Video URL: {video_url}")
                video_hash = video_url.split('/')[-1]
                parsed_url = urlparse(video_url)
                origin = '{uri.scheme}://{uri.netloc}'.format(uri=parsed_url)
                player = '{uri.scheme}://{uri.netloc}/player/index.php?data={0}&do=getVideo'.format(video_hash, uri=parsed_url)
                r = requests.get(video_url, headers={'User-Agent': headers_['User-Agent'], 'sec-fetch-dest': 'iframe'})
                print(f"Video URL response status: {r.status_code}")
                cookies_dict = r.cookies.get_dict()
                cookie_string = urlencode(cookies_dict)
                print(f"Cookies: {cookie_string}")
                r = requests.post(player, headers={'Origin': origin, 'x-requested-with': 'XMLHttpRequest'}, data={'hash': str(video_hash), 'r': r_}, cookies=cookies_dict)
                print(f"Player response status: {r.status_code}")
                src = r.json()
                stream = src['videoSource'] + '|User-Agent=' + quote_plus(headers_['User-Agent']) + '&Cookie=' + quote_plus(cookie_string)
                print(f"Final stream URL: {stream}")
        except Exception as e:
            print(f"Error in movie: {str(e)}")
        return stream

print(VOD().movie('tt0106697'))
print(VOD().tvshows('tt3107288', '1', '1'))


