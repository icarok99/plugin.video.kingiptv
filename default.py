# -*- coding: utf-8 -*-
from lib.helper import *
from lib import xtream, tunein, pluto, imdb, api_vod


# BASIC CONFING
TITULO = '::: KING IPTV :::'
API_CHANNELS = 'https://gitea.com/joel00/kingaddon/raw/branch/main/channels.json'
API_RADIOS = 'https://gitea.com/joel00/kingaddon/raw/branch/main/radios.json'

if not exists(profile):
    try:
        os.mkdir(profile)
    except:
        pass
IPTV_PROBLEM_LOG = translate(os.path.join(profile, 'iptv_problems_log.txt'))


@route('/')
def index():
    addMenuItem({'name': TITULO, 'description': ''}, destiny='')
    addMenuItem({'name': 'LISTAS IPTV', 'description': ''}, destiny='/playlistiptv')
    if six.PY3:
        addMenuItem({'name': 'CANAIS PLUTO', 'description': ''}, destiny='/channels_pluto')
    addMenuItem({'name': 'RADIOS', 'description': ''}, destiny='/radios')
    addMenuItem({'name': 'IMDB Filmes', 'description': ''}, destiny='/imdb_movies')
    addMenuItem({'name': 'IMDB Series', 'description': ''}, destiny='/imdb_series')
    end()
    setview('WideList')

@route('/playlistiptv')
def playlistiptv(): 
    iptv = xtream.parselist(API_CHANNELS)
    if iptv:
        for n, (dns, username, password) in enumerate(iptv):
            n = n + 1
            addMenuItem({'name': 'LISTA {0}'.format(str(n)), 'description': '', 'dns': dns, 'username': str(username), 'password': str(password)}, destiny='/cat_channels')
        end()
        setview('WideList') 
    else:
        notify('Sem lista iptv') 


@route('/cat_channels')
def cat_channels(param):
    dns = param['dns']
    username = param['username']
    password = param['password']
    cat = xtream.API(dns,username,password).channels_category()
    if cat:
        for i in cat:
            name, url = i
            addMenuItem({'name': name, 'description': '', 'dns': dns, 'username': str(username), 'password': str(password), 'url': url}, destiny='/open_channels')
        end()
        setview('WideList')
    else:
        url_problem = '{0}/get.php?username={1}&password={2}\n'.format(dns,username,password)
        if six.PY2:
            import io
            open_file = lambda filename, mode: io.open(filename, mode, encoding='utf-8')
        else:
            open_file = lambda filename, mode: open(filename, mode, encoding='utf-8')
        if exists(IPTV_PROBLEM_LOG):
            check = False
            with open(IPTV_PROBLEM_LOG, "r") as arquivo:
                if url_problem in arquivo.read():
                    check = True
        else:
            check = False
        with open_file(IPTV_PROBLEM_LOG, "a") as arquivo:
            if not check:
                arquivo.write(url_problem)
        notify('Lista Offline')

@route('/open_channels')
def open_channels(param):
    dns = param['dns']
    username = param['username']
    password = param['password']
    url = param['url'] 
    open_ = xtream.API(dns,username,password).channels_open(url)
    if open_:
        setcontent('movies')
        for i in open_:
            name,link,thumb,desc = i
            addMenuItem({'name': name, 'description': desc, 'iconimage': thumb, 'url': link}, destiny='/play_iptv', folder=False)
        end()
        setview('List')
    else:
        notify('Opção indisponivel')

@route('/play_iptv')
def play_iptv(param):
    name = param['name']
    description = param['description']
    iconimage = param['iconimage']
    url = param['url']
    plugin = 'plugin://plugin.video.f4mTester/?streamtype=HLSRETRY&name=' + quote_plus(str(name)) + '&iconImage=' + quote_plus(str(iconimage)) + '&thumbnailImage=' + quote_plus(str(iconimage)) + '&description=' + quote_plus(description) + '&url=' + quote_plus(url)
    xbmc.executebuiltin('RunPlugin(%s)' % plugin)

@route('/channels_pluto')
def channels_pluto():
    channels = pluto.playlist_pluto()
    if channels:
        setcontent('movies')
        for channel in channels:
            channel_name,desc,thumbnail,stream = channel
            addMenuItem({'name': channel_name, 'description': desc, 'iconimage': thumbnail, 'url': stream}, destiny='/play_iptv2', folder=False)
        end()
        setview('List') 



@route('/play_iptv2')
def play_iptv2(param):
    #https://github.com/flubshi/pvr.plutotv/blob/Matrix/src/PlutotvData.cpp
    import inputstreamhelper
    is_helper = inputstreamhelper.Helper("hls")
    if is_helper.check_inputstream():
        url = param.get('url', '')
        if '|' in url:
            header = unquote_plus(url.split('|')[1])
        play_item = xbmcgui.ListItem(path=url)
        play_item.setContentLookup(False)
        play_item.setArt({"icon": "DefaultVideo.png", "thumb": param.get('iconimage', '')})
        play_item.setMimeType("application/vnd.apple.mpegurl")
        if kversion >= 19:
            play_item.setProperty('inputstream', is_helper.inputstream_addon)
        else:
            play_item.setProperty('inputstreamaddon', is_helper.inputstream_addon)
        play_item.setProperty("inputstream.adaptive.manifest_type", "hls")
        if '|' in url:
            play_item.setProperty("inputstream.adaptive.manifest_headers", header)
        play_item.setProperty('inputstream.adaptive.manifest_update_parameter', 'full')
        play_item.setProperty('inputstream.adaptive.is_realtime_stream', 'true')
        if kversion > 19:
            info = play_item.getVideoInfoTag()
            info.setTitle(param.get('name', 'Pluto TV'))
            info.setPlot(param.get('description', ''))
        else:
            play_item.setInfo(type="Video", infoLabels={"Title": param.get('name', ''), "Plot": param.get('description', '')})    
        xbmc.Player().play(item=param.get('url', ''), listitem=play_item)


@route('/radios')
def radios():
    tunein.radios_list(API_RADIOS)

@route('/imdb_movies')
def imdb_series():
    addMenuItem({'name': 'Pesquisar Filmes', 'description': ''}, destiny='/find_movies')
    addMenuItem({'name': 'Filmes - TOP 250', 'description': ''}, destiny='/imdb_movies_250')
    addMenuItem({'name': 'Filmes - Popular', 'description': ''}, destiny='/imdb_movies_popular')
    end()
    setview('WideList')


@route('/imdb_series')
def imdb_series():
    addMenuItem({'name': 'Pesquisar Series', 'description': ''}, destiny='/find_series')
    addMenuItem({'name': 'Series - TOP 250', 'description': ''}, destiny='/imdb_series_250')
    addMenuItem({'name': 'Series - Popular', 'description': ''}, destiny='/imdb_series_popular')
    end()
    setview('WideList') 


@route('/find_movies')
def find_movies():
    search = input_text(heading='Pesquisar')
    if search:
        itens = imdb.IMDBScraper().search_movies(search)
        if itens:
            setcontent('movies')
            for i in itens:
                name,img,page,year,imdb_id = i
                addMenuItem({'name': name, 'description': '', 'iconimage': img, 'url': '', 'imdbnumber': imdb_id}, destiny='/play_resolve_movies', folder=False)
            end()
            setview('Wall') 

@route('/find_series')
def find_series():
    search = input_text(heading='Pesquisar')
    if search:
        itens = imdb.IMDBScraper().search_series(search)
        if itens:
            setcontent('tvshows')
            for i in itens:
                name,img,page,year,imdb_id = i
                addMenuItem({'name': name, 'description': '', 'iconimage': img, 'url': page, 'imdbnumber': imdb_id}, destiny='/open_imdb_seasons')
            end()
            setview('Wall')                 


@route('/imdb_movies_250')
def movies_250():
    itens = imdb.IMDBScraper().movies_250()
    if itens:
        setcontent('movies')
        for i in itens:
            name,image,url,description, imdb_id = i
            addMenuItem({'name': name, 'description': description, 'iconimage': image, 'url': '', 'imdbnumber': imdb_id}, destiny='/play_resolve_movies', folder=False)
        end()
        setview('Wall') 



@route('/imdb_series_250')
def series_250():
    itens = imdb.IMDBScraper().series_250()
    if itens:
        setcontent('tvshows')
        for i in itens:
            name,image,url,description, imdb_id = i
            addMenuItem({'name': name, 'description': description, 'iconimage': image, 'url': url, 'imdbnumber': imdb_id}, destiny='/open_imdb_seasons')
        end()
        setview('Wall')

@route('/imdb_movies_popular')
def movies_popular():
    itens = imdb.IMDBScraper().movies_popular()
    if itens:
        setcontent('movies')
        for i in itens:
            name,image,url,description, imdb_id = i
            addMenuItem({'name': name, 'description': description, 'iconimage': image, 'url': '', 'imdbnumber': imdb_id}, destiny='/play_resolve_movies', folder=False)
        end()
        setview('Wall')  

@route('/imdb_series_popular')
def series_popular():
    itens = imdb.IMDBScraper().series_popular()
    if itens:
        setcontent('tvshows')
        for i in itens:
            name,image,url,description, imdb_id = i
            addMenuItem({'name': name, 'description': description, 'iconimage': image, 'url': url, 'imdbnumber': imdb_id}, destiny='/open_imdb_seasons')
        end()
        setview('Wall') 

@route('/open_imdb_seasons')
def open_imdb_seasons(param):
    serie_icon = param.get('iconimage', '')
    serie_name = param.get('name', '')
    url = param.get('url', '')
    imdb_id = param.get('imdbnumber', '')
    itens = imdb.IMDBScraper().imdb_seasons(url)
    if itens:
        setcontent('tvshows')
        try:
            addMenuItem({'name': '::: ' + serie_name + ':::', 'description': '', 'iconimage': serie_icon}, destiny='')
        except:
            pass
        for i in itens:
            season_number, name, url_season = i
            addMenuItem({'name': name, 'description': '', 'iconimage': serie_icon, 'url': url_season, 'imdbnumber': imdb_id, 'season': season_number, 'serie_name': serie_name}, destiny='/open_imdb_episodes')
        end()
        setview('List')

@route('/open_imdb_episodes')
def open_imdb_episodes(param):
    serie_icon = param.get('iconimage', '')
    serie_name = param.get('serie_name', '')
    url = param.get('url', '')
    imdb_id = param.get('imdbnumber', '')
    season = param.get('season', '')
    itens = imdb.IMDBScraper().imdb_episodes(url)
    if itens:
        setcontent('tvshows')
        try:
            addMenuItem({'name': '::: ' + serie_name + ' - S' + str(season) + ':::', 'description': '', 'iconimage': serie_icon}, destiny='')
        except:
            pass 
        for i in itens:
            episode_number,name,img,fanart,description = i
            name_full = str(episode_number) + ' - ' + name
            #if not '#' in name_full and not '.' in name_full:
            addMenuItem({'name': name_full, 'description': description, 'iconimage': img, 'fanart': fanart, 'imdbnumber': imdb_id, 'season': season, 'episode': str(episode_number), 'serie_name': serie_name, 'playable': 'true'}, destiny='/play_resolve_series', folder=False)
        end()
        setview('List')

@route('/play_resolve_movies')
def play_resolve_movies(param):
    notify('Aguarde')
    # json_rpc_command = '''
    # {
    #     "jsonrpc": "2.0",
    #     "method": "Settings.SetSetting",
    #     "params": {
    #         "setting": "locale.languageaudio",
    #         "value": "por"
    #     },
    #     "id": 1
    # }
    # '''
    # xbmc.executeJSONRPC(json_rpc_command)
    import inputstreamhelper
    #serie_name = param.get('serie_name')
    #season = param.get('season', '')
    #episode = param.get('episode', '')
    iconimage = param.get('iconimage', '')
    imdb = param.get('imdbnumber', '')
    description = param.get('description', '')
    #name = serie_name + ' S' + str(season) + 'E' + str(episode)
    name = param.get('name', '')
    url = api_vod.VOD().movie(imdb)
    if url:
        notify('Escolha o audio portugues nos ajustes')

        is_helper = inputstreamhelper.Helper("hls")
        if is_helper.check_inputstream():
            if '|' in url:
                header = unquote_plus(url.split('|')[1])
            play_item = xbmcgui.ListItem(path=url)
            play_item.setContentLookup(False)
            play_item.setArt({"icon": "DefaultVideo.png", "thumb": iconimage})
            play_item.setMimeType("application/vnd.apple.mpegurl")
            if kversion >= 19:
                play_item.setProperty('inputstream', is_helper.inputstream_addon)
            else:
                play_item.setProperty('inputstreamaddon', is_helper.inputstream_addon)
            play_item.setProperty("inputstream.adaptive.manifest_type", "hls")
            if '|' in url:
                play_item.setProperty("inputstream.adaptive.manifest_headers", header)
            play_item.setProperty('inputstream.adaptive.manifest_update_parameter', 'full')
            play_item.setProperty('inputstream.adaptive.is_realtime_stream', 'true')
            play_item.setProperty('inputstream.adaptive.original_audio_language', 'pt') 
            if kversion > 19:
                info = play_item.getVideoInfoTag()
                info.setTitle(name)
                info.setPlot(description)
                info.setIMDBNumber(str(imdb))
                #info.setSeason(int(season))
                #info.setEpisode(int(episode))
            else:
                play_item.setInfo(type="Video", infoLabels={"Title": name, "Plot": description})
                play_item.setInfo('video', {'imdbnumber': str(imdb)})
                #play_item.setInfo('video', {'season': int(season)})
                #play_item.setInfo('video', {'episode': int(episode)})

            #xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, play_item)
            xbmc.Player().play(item=url, listitem=play_item)
    else:
        notify('Stream Indisponivel') 

@route('/play_resolve_series')
def play_resolve_series(param):
    notify('Aguarde')
    # json_rpc_command = '''
    # {
    #     "jsonrpc": "2.0",
    #     "method": "Settings.SetSetting",
    #     "params": {
    #         "setting": "locale.languageaudio",
    #         "value": "por"
    #     },
    #     "id": 1
    # }
    # '''
    # xbmc.executeJSONRPC(json_rpc_command)
    import inputstreamhelper
    serie_name = param.get('serie_name')
    season = param.get('season', '')
    episode = param.get('episode', '')
    iconimage = param.get('iconimage', '')
    imdb = param.get('imdbnumber', '')
    description = param.get('description', '')
    name = serie_name + ' S' + str(season) + 'E' + str(episode)
    url = api_vod.VOD().tvshows(imdb,season,episode)
    if url:
        notify('Escolha o audio portugues nos ajustes')

        is_helper = inputstreamhelper.Helper("hls")
        if is_helper.check_inputstream():
            if '|' in url:
                header = unquote_plus(url.split('|')[1])
            play_item = xbmcgui.ListItem(path=url)
            play_item.setContentLookup(False)
            play_item.setArt({"icon": "DefaultVideo.png", "thumb": iconimage})
            play_item.setMimeType("application/vnd.apple.mpegurl")
            if kversion >= 19:
                play_item.setProperty('inputstream', is_helper.inputstream_addon)
            else:
                play_item.setProperty('inputstreamaddon', is_helper.inputstream_addon)
            play_item.setProperty("inputstream.adaptive.manifest_type", "hls")
            if '|' in url:
                play_item.setProperty("inputstream.adaptive.manifest_headers", header)
            play_item.setProperty('inputstream.adaptive.manifest_update_parameter', 'full')
            play_item.setProperty('inputstream.adaptive.is_realtime_stream', 'true')
            play_item.setProperty('inputstream.adaptive.original_audio_language', 'pt') 
            if kversion > 19:
                info = play_item.getVideoInfoTag()
                info.setTitle(name)
                info.setPlot(description)
                info.setIMDBNumber(str(imdb))
                info.setSeason(int(season))
                info.setEpisode(int(episode))
            else:
                play_item.setInfo(type="Video", infoLabels={"Title": name, "Plot": description})
                play_item.setInfo('video', {'imdbnumber': str(imdb)})
                play_item.setInfo('video', {'season': int(season)})
                play_item.setInfo('video', {'episode': int(episode)})

            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, play_item)
    else:
        notify('Stream Indisponivel')  



