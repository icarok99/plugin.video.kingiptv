# -*- coding: utf-8 -*-
try:
    from lib.helper import *
except Exception:
    from helper import *

import uuid
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

try:
    from lib.ClientScraper import cfscraper, USER_AGENT
except Exception:
    try:
        from ClientScraper import cfscraper, USER_AGENT
    except Exception:
        cfscraper = None
        USER_AGENT = 'Mozilla/5.0 (Kodi Addon)'

def _parse_iso_datetime(s):
    if not s:
        return None
    s = s.strip()
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    s = re.sub(r'([+-]\d{2}:\d)(?!\d)', lambda m: m.group(1) + '0', s)
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        for fmt in ('%Y-%m-%dT%H:%M:%S.%f%z', '%Y-%m-%dT%H:%M:%S%z'):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue
    return None

def get_current_time():
    try:
        resp = requests.get('https://worldtimeapi.org/api/timezone/America/Sao_Paulo', timeout=6)
        resp.raise_for_status()
        data = resp.json()
        dt_str = data.get('datetime')
        dt = _parse_iso_datetime(dt_str)
        if dt is None:
            raise ValueError
        return dt
    except Exception:
        return datetime.now(timezone.utc)

def playlist_pluto():
    channels_kodi = []
    try:
        deviceid = str(uuid.uuid4())
        time_brazil = get_current_time()
        from_utc = time_brazil.astimezone(timezone.utc)
        to_utc = (time_brazil + timedelta(days=1)).astimezone(timezone.utc)
        from_str = from_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
        to_str = to_utc.strftime('%Y-%m-%dT%H:%M:%SZ')

        url = f'https://api.pluto.tv/v2/channels?start={from_str}&stop={to_str}'
        if cfscraper:
            channels = cfscraper.get(url).json()
        else:
            headers = {'User-Agent': USER_AGENT}
            channels = requests.get(url, headers=headers, timeout=10).json()

        for channel in channels:
            number = channel.get('number', 0)
            if not number or int(number) <= 0:
                continue

            channel_name = channel.get('name', f'#{number}')
            thumb = channel.get('logo', {}).get('path', '')
            stream_url = None

            stitched_urls = channel.get('stitched', {}).get('urls', [])
            if stitched_urls:
                stream_url = stitched_urls[0].get('url')
                if stream_url:
                    stream_url = stream_url.replace('&deviceMake=', '&deviceMake=Firefox')
                    stream_url = stream_url.replace('&deviceType=', '&deviceType=web')
                    stream_url = stream_url.replace('&deviceId=unknown', f'&deviceId={deviceid}')
                    stream_url = stream_url.replace('&deviceModel=', '&deviceModel=web')
                    stream_url = stream_url.replace('&deviceVersion=unknown', '&deviceVersion=82.0')
                    stream_url = stream_url.replace('&appName=&', '&appName=web&')
                    stream_url = stream_url.replace('&appVersion=&', '&appVersion=5.9.1-e0b37ef76504d23c6bdc8157813d13333dfa33a3')
                    stream_url = stream_url.replace('&sid=', f'&sid={deviceid}&sessionID={deviceid}')
                    stream_url = stream_url.replace('&deviceDNT=0', '&deviceDNT=false')
                    stream_url = f"{stream_url}&serverSideAds=false&terminate=false&clientDeviceType=0&clientModelNumber=na&clientID={deviceid}"
                    stream_url = stream_url + '|User-Agent=' + quote_plus(USER_AGENT)

            timelines = channel.get('timelines', [])
            current_program = None
            next_program = None
            for idx, t in enumerate(timelines):
                start = _parse_iso_datetime(t.get('start'))
                stop = _parse_iso_datetime(t.get('stop'))
                if not start or not stop:
                    continue
                if start <= time_brazil <= stop:
                    ep = t.get('episode', {})
                    current_program = {
                        'title': ep.get('name', ''),
                        'description': ep.get('description', ''),
                        'start': start,
                        'stop': stop
                    }
                    if idx + 1 < len(timelines):
                        nt = timelines[idx + 1]
                        ns = _parse_iso_datetime(nt.get('start'))
                        ne = _parse_iso_datetime(nt.get('stop'))
                        nep = nt.get('episode', {})
                        next_program = {
                            'title': nep.get('name', ''),
                            'description': nep.get('description', ''),
                            'start': ns,
                            'stop': ne
                        }
                    break

            desc = ''
            if current_program:
                local_now = current_program['start'].astimezone(timezone(timedelta(hours=-3)))
                desc += f"[COLOR yellow][{local_now.strftime('%H:%M')}] {current_program['title']}[/COLOR]\n({current_program['description']})\n"
            if next_program:
                local_next = next_program['start'].astimezone(timezone(timedelta(hours=-3)))
                desc += f"[COLOR yellow][{local_next.strftime('%H:%M')}] {next_program['title']}[/COLOR]\n({next_program['description']})\n"

            name_for_kodi = channel_name
            if current_program and current_program.get('title'):
                name_for_kodi = f"{channel_name} - [COLOR yellow]{current_program.get('title')}[/COLOR]"

            channels_kodi.append((name_for_kodi, desc, thumb, stream_url))

    except Exception as e:
        log(f'playlist_pluto: erro geral: {e}')
        raise

    return channels_kodi
