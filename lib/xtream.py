# -*- coding: utf-8 -*-
import xml.etree.ElementTree as ET
import base64
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
try:
    from lib.helper import *
except:
    from helper import *
import re
import time
from urllib.parse import urlparse, parse_qs

IPTV_PROBLEM_LOG = translate(os.path.join(profile, 'iptv_problems_log.txt'))

REQUEST_TIMEOUT = 10
MAX_RETRIES = 1
CACHE_FAILED_URLS = {}

def create_session():
    session = requests.Session()
    retry = Retry(
        total=MAX_RETRIES,
        read=MAX_RETRIES,
        connect=MAX_RETRIES,
        backoff_factor=0.3,
        status_forcelist=(500, 502, 504)
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    return session

def log_iptv_problem(url, error_msg=''):
    try:
        if six.PY2:
            import io
            open_file = lambda filename, mode: io.open(filename, mode, encoding='utf-8')
        else:
            open_file = lambda filename, mode: open(filename, mode, encoding='utf-8')
        
        with open_file(IPTV_PROBLEM_LOG, "a") as arquivo:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            arquivo.write('{0} - {1} - {2}\n'.format(timestamp, url, error_msg))
    except:
        pass

def extract_info(url):
    try:
        parsed_url = urlparse(url)
        protocol = parsed_url.scheme
        host = parsed_url.hostname
        
        if not host:
            return None, None, None
        
        if parsed_url.port:
            port = parsed_url.port
        else:
            port = 80 if parsed_url.scheme == 'http' else 443
        
        query_params = parse_qs(parsed_url.query)
        username = query_params.get('username', [None])[0]
        password = query_params.get('password', [None])[0]
        
        if not username or not password:
            log_iptv_problem(url, 'URL sem username ou password válidos')
            return None, None, None
        
        dns = '{0}://{1}:{2}'.format(protocol, host, port)
        
        return dns, username, password
    except Exception as e:
        log_iptv_problem(url, 'Erro ao extrair info: {0}'.format(str(e)))
        return None, None, None

def check_iptv(url_iptv):
    current_time = time.time()
    if url_iptv in CACHE_FAILED_URLS:
        if current_time - CACHE_FAILED_URLS[url_iptv] < 300:
            return False
    
    cond = True
    if exists(IPTV_PROBLEM_LOG):
        try:
            if six.PY2:
                import io
                open_file = lambda filename, mode: io.open(filename, mode, encoding='utf-8')
            else:
                open_file = lambda filename, mode: open(filename, mode, encoding='utf-8')
            
            with open_file(IPTV_PROBLEM_LOG, "r") as arquivo:
                urls = arquivo.read()
                urls = urls.split('\n')
                for i in urls:
                    if 'http' in i and i in url_iptv:
                        cond = False
                        break
        except:
            pass
    return cond

def parselist(url):
    iptv = []
    session = create_session()
    
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        url = response.json()['url']
    except:
        pass
    
    try:
        if 'paste.kodi.tv' in url and 'documents' not in url and 'raw' not in url:
            try:
                key = url.split('/')[-1]
                url = 'https://paste.kodi.tv/documents/' + key
                response = session.get(url, timeout=REQUEST_TIMEOUT)
                src = response.json()['data']
                lines = src.split('\n')
                
                for i in lines:
                    i = i.replace(' ', '')
                    if 'http' in i:
                        if check_iptv(i):
                            dns, username, password = extract_info(i)
                            if dns and username and password:
                                iptv.append((dns, username, password))
            except Exception as e:
                log_iptv_problem(url, 'Erro paste.kodi.tv: {0}'.format(str(e)))
        else:
            response = session.get(url, timeout=REQUEST_TIMEOUT)
            src = response.text
            lines = src.split('\n')
            
            for i in lines:
                i = i.replace(' ', '')
                if 'http' in i:
                    if check_iptv(i):
                        dns, username, password = extract_info(i)
                        if dns and username and password:
                            iptv.append((dns, username, password))
    except Exception as e:
        log_iptv_problem(url, 'Erro parselist: {0}'.format(str(e)))
    
    return iptv

def clean_channel_name(name):
    if not name:
        return name
    
    name = re.sub(r'\s*\[\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}\]', '', name)
    name = re.sub(r'\s*\+\s*\d+\.?\d*\s*min', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    
    tags_inicio = []
    resto = name
    
    while True:
        match = re.match(r'^(\[[^\]]+\])\s*', resto)
        if match:
            tags_inicio.append(match.group(1))
            resto = resto[match.end():]
        else:
            break
    
    if not resto:
        return name
    
    sufixos_canal = [
        'HD', 'FHD', 'SD', '4K', 'UHD', 'HD+', 'HD¹', 'HD²', 'HD2', 'HD1',
        'FHD¹', 'FHD²', 'SD¹', 'SD²', '4K¹', '4K²', 'UHD¹', 'UHD²',
        'H264', 'H265', 'H264¹', 'H264²', 'H265¹', 'H265²',
        'PLUS', 'PLUS¹', 'PLUS²', 'PREMIUM', 'PREMIUM¹', 'PREMIUM²',
        'MAX', 'MAX¹', 'MAX²'
    ]
    
    palavras = resto.split()
    ultimo_sufixo_idx = -1
    
    for idx, palavra in enumerate(palavras):
        palavra_limpa = re.sub(r'[¹²+]', '', palavra.upper())
        
        if palavra.upper() in sufixos_canal or palavra_limpa in sufixos_canal:
            ultimo_sufixo_idx = idx
    
    if ultimo_sufixo_idx >= 0:
        canal_palavras = palavras[:ultimo_sufixo_idx + 1]
        canal_str = ' '.join(canal_palavras)
        
        if tags_inicio:
            name = ' '.join(tags_inicio) + ' ' + canal_str
        else:
            name = canal_str
    
    if '-' in name:
        name = re.sub(r'\s*-\s*', ' - ', name)
    
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name

def ordenar_resolucao(item):
    name = item[0]
    if 'FHD' in name:
        return 1
    elif 'HD' in name:
        return 2
    elif '4K' in name:
        return 3    
    elif 'SD' in name:
        return 4
    return 5 

class API:
    def __init__(self, dns, username, password, hide_adult='true'):
        
        if not username or not password:
            raise ValueError('Username e password são obrigatórios')
        
        self.dns = dns
        self.username = username
        self.password = password
        self.player_api = '{0}/player_api.php?username={1}&password={2}'.format(dns, username, password)
        self.play_url = '{0}/live/{1}/{2}/'.format(dns, username, password)
        self.play_movies = '{0}/movie/{1}/{2}/'.format(dns, username, password)
        self.play_series = '{0}/series/{1}/{2}/'.format(dns, username, password)
        self.adult_tags = ['xxx','xXx','XXX','adult','Adult','ADULT','adults','Adults','ADULTS','porn','Porn','PORN', 'teste', 'TESTE', 'Teste']
        self.hide_adult = hide_adult
        self.server_alive = None
        self.server_format = None
        self.session = create_session()
        
        self.live_url = '{0}/enigma2.php?username={1}&password={2}&type=get_live_categories'.format(dns, username, password)
        self.vod_url = '{0}/enigma2.php?username={1}&password={2}&type=get_vod_categories'.format(dns, username, password)
        self.series_url = '{0}/enigma2.php?username={1}&password={2}&type=get_series_categories'.format(dns, username, password)

    def check_server_alive(self):
        if self.server_alive is not None:
            return self.server_alive
        
        try:
            response = self.session.get(self.player_api, timeout=10, allow_redirects=False)
            status = response.status_code
            
            if status == 200:
                self.server_alive = True
                self.server_format = 'xtream'
                
                try:
                    test_session = requests.Session()
                    test_session.headers.update(self.session.headers)
                    response_enigma = test_session.get(self.live_url, timeout=3, allow_redirects=False)
                    
                    if response_enigma.status_code == 200:
                        self.server_format = 'enigma2'
                except requests.exceptions.Timeout:
                    pass
                except:
                    pass
                
                return True
        except Exception:
            pass
        
        try:
            response = self.session.get(self.live_url, timeout=10, allow_redirects=False)
            status = response.status_code
            
            if status == 200:
                self.server_alive = True
                self.server_format = 'enigma2'
                return True
        except Exception:
            pass
        
        self.server_alive = False
        self.server_format = None
        log_iptv_problem(self.dns, 'Servidor não responde em nenhum formato (player_api ou enigma2)')
        CACHE_FAILED_URLS[self.dns] = time.time()
        return False

    def http(self, url='', mode=None):
        if not self.check_server_alive():
            return '' if mode != 'json_url' else None
        
        try:
            if not mode:
                response = self.session.get(url, timeout=REQUEST_TIMEOUT)
                if response.status_code != 200:
                    raise requests.exceptions.HTTPError('Status code: {}'.format(response.status_code))
                return response.content
                
            elif mode == 'channels_category':
                if self.server_format != 'enigma2':
                    return ''
                
                response = self.session.get(self.live_url, timeout=REQUEST_TIMEOUT)
                if response.status_code != 200:
                    raise requests.exceptions.HTTPError('Status code: {}'.format(response.status_code))
                return response.content
                
            elif mode == 'json_url':
                response = self.session.get(url, timeout=REQUEST_TIMEOUT)
                if response.status_code != 200:
                    raise requests.exceptions.HTTPError('Status code: {}'.format(response.status_code))
                data = response.json()
                return data
                
            elif mode == 'vod':
                if self.server_format != 'enigma2':
                    return ''
                
                response = self.session.get(url, timeout=REQUEST_TIMEOUT)
                if response.status_code != 200:
                    raise requests.exceptions.HTTPError('Status code: {}'.format(response.status_code))
                return response.text
                
        except requests.exceptions.Timeout:
            log_iptv_problem(url or self.live_url, 'Timeout ao fazer requisição')
            CACHE_FAILED_URLS[url or self.live_url] = time.time()
            
        except requests.exceptions.ConnectionError as e:
            log_iptv_problem(url or self.live_url, 'Erro de conexão: {0}'.format(str(e)))
            CACHE_FAILED_URLS[url or self.live_url] = time.time()
            
        except requests.exceptions.HTTPError as e:
            log_iptv_problem(url or self.live_url, 'Erro HTTP: {0}'.format(str(e)))
            CACHE_FAILED_URLS[url or self.live_url] = time.time()
            
        except requests.exceptions.RequestException as e:
            log_iptv_problem(url or self.live_url, 'Erro de requisição: {0}'.format(str(e)))
            CACHE_FAILED_URLS[url or self.live_url] = time.time()
            
        except Exception as e:
            log_iptv_problem(url or self.live_url, 'Erro inesperado: {0}'.format(str(e)))
        
        return '' if mode != 'json_url' else None

    def b64(self, obj):
        try:
            return base64.b64decode(obj).decode('utf-8')
        except:
            return str(obj)
    
    def check_protocol(self, url):
        try:
            parsed = urlparse(self.live_url)
            protocol = parsed.scheme
            if protocol == 'https':
                return url.replace('http://', 'https://')
            return url
        except:
            return url
    
    def regex_from_to(self, text, from_string, to_string, excluding=True):
        if excluding:
            try:
                r = re.search(r"(?i)" + from_string + r"([\S\s]+?)" + to_string, text).group(1)
            except:
                r = ''
        else:
            try:
                r = re.search(r"(?i)(" + from_string + r"[\S\s]+?" + to_string + r")", text).group(1)
            except:
                r = ''
        return r 

    def regex_get_all(self, text, start_with, end_with):
        try:
            r = re.findall(r"(?i)(" + start_with + r"[\S\s]+?" + end_with + r")", text)
            return r
        except:
            return []

    def channels_category(self):
        itens = []
        
        if not self.check_server_alive():
            return itens
        
        if self.server_format == 'enigma2':
            xml_data = self.http('', 'channels_category')
            
            if not xml_data:
                return itens
            
            try:
                root = ET.fromstring(xml_data)
                channels = root.findall('channel')
                
                if not channels:
                    return itens
                
                for channel in channels:
                    try:
                        name_elem = channel.find('title')
                        url_elem = channel.find('playlist_url')
                        if name_elem is not None and url_elem is not None:
                            name = self.b64(name_elem.text)
                            url = self.check_protocol(url_elem.text.replace('<![CDATA[', '').replace(']]>', ''))
                            
                            if 'All' not in name:
                                if self.hide_adult == 'false':
                                    itens.append((name, url))
                                else:
                                    if not any(s in name for s in self.adult_tags):
                                        itens.append((name, url))
                    except Exception as e:
                        log_iptv_problem(self.live_url, 'Erro ao processar categoria: {0}'.format(str(e)))
                        continue
                        
            except Exception as e:
                log_iptv_problem(self.live_url, 'Erro ao parsear XML de categorias: {0}'.format(str(e)))
        
        elif self.server_format == 'xtream':
            url_categories = '{0}&action=get_live_categories'.format(self.player_api)
            categories = self.http(url_categories, 'json_url')
            
            if not categories:
                return itens
            
            try:
                for cat in categories:
                    try:
                        name = cat.get('category_name', '')
                        cat_id = cat.get('category_id', '')
                        
                        if not cat_id:
                            continue
                        
                        url = '{0}&action=get_live_streams&category_id={1}'.format(
                            self.player_api, cat_id
                        )
                        
                        if 'All' not in name:
                            if self.hide_adult == 'false':
                                itens.append((name, url))
                            else:
                                if not any(s in name for s in self.adult_tags):
                                    itens.append((name, url))
                    except Exception as e:
                        log_iptv_problem(url_categories, 'Erro ao processar categoria: {0}'.format(str(e)))
                        continue
            except Exception as e:
                log_iptv_problem(url_categories, 'Erro ao processar categorias: {0}'.format(str(e)))
        
        return itens
    
    def channel_id(self, json_data, n):
        if json_data and isinstance(json_data, list):
            try:
                if n < len(json_data):
                    return json_data[n].get('stream_id', '')
            except:
                pass
        return ''

    def channels_open(self, url):
        itens = []
        
        if 'player_api.php' in url and 'action=get_live_streams' in url:
            json_data = self.http(url, 'json_url')
            
            if not json_data:
                return itens
            
            try:
                for stream in json_data:
                    try:
                        name = stream.get('name', '')
                        stream_id = stream.get('stream_id', '')
                        
                        if not stream_id:
                            continue
                        
                        name = clean_channel_name(name)
                        url_ = '{0}{1}.m3u8'.format(self.play_url, stream_id)
                        
                        thumb = stream.get('stream_icon', '')
                        desc = ''
                        
                        itens.append((name, url_, thumb, desc))
                    except Exception as e:
                        log_iptv_problem(url, 'Erro ao processar stream: {0}'.format(str(e)))
                        continue
                
                if itens:
                    itens = sorted(itens, key=lambda x: x[0].lower())
                    
            except Exception as e:
                log_iptv_problem(url, 'Erro ao processar streams: {0}'.format(str(e)))
            
            return itens
        
        try:
            chan_id = url.split('cat_id=')[1].split('&')[0]
        except:
            try:
                chan_id = url.split('category_id=')[1].split('&')[0]
            except:
                chan_id = ''

        if not chan_id:
            return itens
        
        xml_data = self.http(url)
        
        if not xml_data:
            return itens
        
        try:
            url_json_channels = '{0}&action=get_live_streams&category_id={1}'.format(
                self.player_api, chan_id
            )
            json_data = self.http(url_json_channels, 'json_url')
            
            root = ET.fromstring(xml_data)
            channels = root.findall('channel')
            
            if not channels:
                return itens
            
            for i, channel in enumerate(channels):
                try:
                    title_elem = channel.find('title')
                    if title_elem is None:
                        continue
                    
                    name = self.b64(title_elem.text)
                    name = clean_channel_name(name)
                    
                    stream_id = self.channel_id(json_data, i)
                    
                    if not stream_id:
                        continue
                    
                    url_ = '{0}{1}.m3u8'.format(self.play_url, stream_id)
                    
                    try:
                        desc_image_elem = channel.find('desc_image')
                        description_elem = channel.find('description')
                        thumb = desc_image_elem.text.replace('<![CDATA[ ', '').replace(' ]]>', '') if desc_image_elem is not None else ''
                        desc = ''
                    except:
                        thumb = ''
                        desc = ''
                    
                    itens.append((name, url_, thumb, desc))
                    
                except Exception as e:
                    log_iptv_problem(url, 'Erro ao processar canal {0}: {1}'.format(i, str(e)))
                    continue
            
            if itens:
                itens = sorted(itens, key=lambda x: x[0].lower())
                    
        except Exception as e:
            log_iptv_problem(url, 'Erro ao abrir canais: {0}'.format(str(e)))
        
        return itens

    def series_cat(self):
        itens = []
        url_series = '{0}&action=get_series_categories'.format(self.player_api)
        vod_cat = self.http(url_series, 'json_url')
        
        if not vod_cat:
            return itens
        
        try:
            for cat in vod_cat:
                try:
                    name = cat['category_name']
                    url = '{0}&action=get_series&category_id={1}'.format(
                        self.player_api, cat['category_id']
                    )
                    
                    if self.hide_adult == 'false':
                        itens.append((name, url))
                    else:
                        if not any(s in name for s in self.adult_tags):
                            itens.append((name, url))
                except:
                    continue
        except Exception as e:
            log_iptv_problem(url_series, 'Erro ao processar categorias de séries: {0}'.format(str(e)))
        
        return itens
    
    def series_list(self, url):
        itens = []
        ser_cat = self.http(url, 'json_url')
        
        if not ser_cat:
            return itens
        
        try:
            for ser in ser_cat:
                try:
                    name = ser.get('name', '')
                    series_id = ser.get('series_id', '')
                    
                    if not series_id:
                        continue
                    
                    url = '{0}&action=get_series_info&series_id={1}'.format(
                        self.player_api, str(series_id)
                    )
                    
                    thumb = ser.get('cover', '')
                    background = ser.get('backdrop_path', [''])[0] if ser.get('backdrop_path') else ''
                    plot = ser.get('plot', '')
                    releaseDate = ser.get('releaseDate', '')
                    cast = str(ser.get('cast', '')).split()
                    rating_5based = ser.get('rating_5based', '')
                    episode_run_time = str(ser.get('episode_run_time', ''))
                    genre = ser.get('genre', '')
                    
                    itens.append((name, url, thumb, background, plot, releaseDate, cast, rating_5based, episode_run_time, genre))
                except:
                    continue
        except Exception as e:
            log_iptv_problem(url, 'Erro ao listar séries: {0}'.format(str(e)))
        
        return itens
    
    def series_seasons(self, url):
        itens = []
        ser_cat = self.http(url, 'json_url')
        
        if not ser_cat or 'episodes' not in ser_cat:
            return itens
        
        try:
            info = ser_cat.get('info', {})
            thumb = info.get('cover', '')
            background = info.get('backdrop_path', [''])[0] if info.get('backdrop_path') else ''
            
            for ser in ser_cat['episodes']:
                try:
                    name = 'Season - ' + str(ser)
                    url_ = '{0}&season_number={1}'.format(url, str(ser))
                    itens.append((name, url_, thumb, background))
                except:
                    continue
        except Exception as e:
            log_iptv_problem(url, 'Erro ao obter temporadas: {0}'.format(str(e)))
        
        return itens
    
    def season_list(self, url):
        itens = []
        ser_cat = self.http(url, 'json_url')
        
        if not ser_cat or 'episodes' not in ser_cat:
            return itens
        
        try:
            info = ser_cat.get('info', {})
            episodes = ser_cat['episodes']
            
            parsed_url = urlparse(url)
            season_number = str(parse_qs(parsed_url.query)['season_number'][0])
            
            if season_number not in episodes:
                return itens
            
            for ser in episodes[season_number]:
                try:
                    episode_id = ser.get('id', '')
                    extension = ser.get('container_extension', 'mp4')
                    
                    if not episode_id:
                        continue
                    
                    play_url = '{0}{1}.{2}'.format(self.play_series, str(episode_id), extension)
                    name = ser.get('title', '')
                    
                    episode_info = ser.get('info', {})
                    thumb = episode_info.get('movie_image', '')
                    background = episode_info.get('movie_image', '')
                    plot = episode_info.get('plot', '')
                    releasedate = episode_info.get('releasedate', '')
                    cast = str(info.get('cast', '')).split()
                    rating_5based = info.get('rating_5based', '')
                    duration = str(episode_info.get('duration', ''))
                    genre = info.get('genre', '')
                    
                    itens.append((name, play_url, thumb, background, plot, releasedate, cast, rating_5based, duration, genre))
                except:
                    continue
        except Exception as e:
            log_iptv_problem(url, 'Erro ao listar episódios: {0}'.format(str(e)))
        
        return itens

    def vod(self, url=''):
        itens = []
        
        if not url:
            open_data = self.http(self.vod_url, mode='vod')
        else:
            open_data = self.http(url, 'vod')
        
        if not open_data:
            return itens
        
        try:
            all_cats = self.regex_get_all(open_data, '<channel>', '</channel>')
            
            if not all_cats:
                return itens
            
            for a in all_cats:
                try:
                    if '<playlist_url>' in open_data:
                        name = str(self.b64(self.regex_from_to(a, '<title>', '</title>'))).replace('?', '')
                        vod_url = self.check_protocol(
                            self.regex_from_to(a, '<playlist_url>', '</playlist_url>')
                            .replace('<![CDATA[', '').replace(']]>', '')
                        )
                        
                        if 'All' not in name:
                            if self.hide_adult == 'false':
                                itens.append(('dir', name, vod_url))
                            else:
                                if not any(s in name for s in self.adult_tags):
                                    itens.append(('dir', name, vod_url))
                    else:
                        name = self.b64(self.regex_from_to(a, '<title>', '</title>'))
                        thumb = self.regex_from_to(a, '<desc_image>', '</desc_image>').replace('<![CDATA[', '').replace(']]>', '')
                        vod_url = self.check_protocol(
                            self.regex_from_to(a, '<stream_url>', '</stream_url>')
                            .replace('<![CDATA[', '').replace(']]>', '')
                        )
                        desc = self.b64(self.regex_from_to(a, '<description>', '</description>'))
                        plot = self.regex_from_to(desc, 'PLOT:', '\n')
                        cast = self.regex_from_to(desc, 'CAST:', '\n') or ('', '')
                        ratin = self.regex_from_to(desc, 'RATING:', '\n')
                        year = self.regex_from_to(desc, 'RELEASEDATE:', '\n').replace(' ', '-')
                        year_match = re.compile('-.*?-.*?-(.*?)-', re.DOTALL).findall(year)
                        year = str(year_match).replace("['", "").replace("']", "") if year_match else ''
                        runt = self.regex_from_to(desc, 'DURATION_SECS:', '\n')
                        genre = self.regex_from_to(desc, 'GENRE:', '\n')
                        background = ''
                        
                        cast_list = str(cast).split() if cast else ('', '')
                        
                        itens.append(('play', name, vod_url, thumb, background, plot, year, cast_list, ratin, genre))
                except:
                    continue
        except Exception as e:
            log_iptv_problem(url or self.vod_url, 'Erro ao processar VOD: {0}'.format(str(e)))
        
        return itens
