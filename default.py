#
#      Copyright (C) 2013 Sean Poyser
#      Patched by Kodibear (kodibeardev@gmail.com)
#
#  This Program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2, or (at your option)
#  any later version.
#
#  This Program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with XBMC; see the file COPYING.  If not, write to
#  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
#  http://www.gnu.org/copyleft/gpl.html
#

import urllib
import urllib2
import random
import re
import os
import net

import xbmc
import xbmcaddon
import xbmcplugin
import xbmcgui

import resolve
import wco_utils as utils

# import pydevd
# pydevd.settrace(stdoutToServer=True, stderrToServer=True)

import CommonFunctions
common = CommonFunctions

ADDONID = utils.ADDONID
ADDON   = utils.ADDON
HOME    = utils.HOME
PROFILE = utils.PROFILE
TITLE   = utils.TITLE
VERSION = utils.VERSION
ARTWORK = utils.ARTWORK
ICON    = utils.ICON
URL     = utils.URL


SECTION       = 100
SERIES        = 200
EPISODE       = 300
HOST          = 400
DOWNLOAD      = 500
MARKWATCHED   = 600
MARKUNWATCHED = 601
SEARCH   = 700

AUTOPLAY = ADDON.getSetting('AUTOPLAY') == 'true'

import metadata
meta = metadata.metadata()
meta.SetDir(os.path.join(PROFILE ,'watched'))


def CheckVersion():
    prev = ADDON.getSetting('VERSION')
    curr = VERSION

    if prev == curr:
        return

    ADDON.setSetting('VERSION', curr)

    if curr == '1.0.17':
        d = xbmcgui.Dialog()
        d.ok(TITLE + ' - ' + VERSION, 'Welcome to Watch Cartoon Online', 'Now with download feature.', '')


class XBMCPlayer(xbmc.Player):
    def __init__( self, *args, **kwargs ):
        self.is_active = True
        
    def SetMetaData(self, metaData):
        self.metaData = metaData

    #don't flag as watched if stopped
    #def onPlayBackStopped(self):
    #    self.onPlayBackEnded()
                
    def onPlayBackEnded(self):
        self.is_active = False
        meta.SetWatchedStatus(self.metaData, True)
        xbmc.executebuiltin('XBMC.Container.Refresh')


def Main():
    CheckVersion()

    html = utils.getHTML(URL)

    match = re.compile('<li><a href="(.+?)">(.+?)</a></li>').findall(html)
    for url, name in match:
        if name == 'Contact':
            break
        if name != 'Home':
            AddSection(name, '', url)
    
    AddDir('Search', SEARCH, '', ICON, isFolder=True)

def Search():
    searchString = xbmcgui.Dialog().input('Search WatchCartoonOnline', type=xbmcgui.INPUT_ALPHANUM)
    netApi = net.Net()
    netApi.set_user_agent(utils.getUserAgent())
    
    url = 'https://www.watchcartoononline.io/search'
    data = { 'catara': searchString, 'konuara': 'series' }

    html = netApi.http_POST(url, data).content
    hits = common.parseDOM(html, "div", attrs = { "class": "iccerceve" })
    
    for hit in hits:
        hit = hit.split('</div>', 1)[-1]
        hitUrl = common.parseDOM(hit, 'a', ret='href')[0].encode("utf-8")
        hitTitle = common.parseDOM(hit, 'a', ret='title')[0].encode("utf-8")
        hitImage = common.parseDOM(hit, 'img', ret='src')[0].encode("utf-8")
        
        AddDir(hitTitle, SERIES, url=hitUrl, image=hitImage, isFolder=True)
    
def DoSection(url):
    mode = SERIES
    if url == 'http://www.watchcartoononline.com/movie-list':
        mode = EPISODE
    if url == 'http://www.watchcartoononline.com/ova-list':
        mode = EPISODE

    html = utils.getHTML(url)

    html = html.split('<div id="ddmcc_container">', 1)[-1]

    html = html.replace('<li><a href=""></a></li>', '')
  
    names = []

    match = re.compile('<li><a href="(.+?)" title="(.+?)">(.+?)</a></li>').findall(html)

    sorted = []

    for url, name in match:
        if '#' not in url:
            if name not in names:
                names.append(name)
                if mode == SERIES:
                    newName = name
                    if newName.startswith('The '):
                        newName = newName.split('The ', 1)[-1]
                    sorted.append([newName, name, url])
                elif mode == EPISODE:
                    AddEpisode(name, url)

    sorted.sort()
    for item in sorted:
        AddSeries(item[1], item[2])

def DoSeries(html):
    try:
        image = common.parseDOM(common.parseDOM(html, "div", attrs = { "id": "cat-img-desc" }), "img", ret="src")[0]
        html = common.parseDOM(html, "div", attrs = { "id": "catlist-listview" })[0]
        match = re.compile('<li>(.+?)</li>').findall(html)

        for item in match:
            url = common.parseDOM(item, "a", ret = "href")[0].encode("utf-8")
            name = common.parseDOM(item, "a")[0].encode("utf-8")
            AddEpisode(name, url, image)
    except:
        pass

def GetLinkIndex(resolved, select):
    if len(resolved) < 2 or (not select):
        return 0

    current = ''
    prev    = ''
    part    = 1

    hosts = []

    for item in resolved:
        resolver = item[0]

        if resolver == current:
            hosts[-1] = resolver + ' # %d %s' % (part, prev)
            part     += 1
            hosts.append(resolver + ' # %d %s' % (part,  item[2]))
        else:
            current = resolver
            part    = 1
            hosts.append(resolver + ' %s' % item[2])

        prev = item[2]

    index = xbmcgui.Dialog().select('Please Select Video Host', hosts)   
        
    if index < 0:
        return None

    return index


def selectHost(url):
    PlayVideo(url, True)


def DownloadVideo(_url,  title):
    resolved = resolve.ResolveURL(_url)

    title = utils.clean(title)

    if len(resolved) == 0:
        d = xbmcgui.Dialog()
        d.ok(TITLE + ' - ' + VERSION, 'Unable to download', title, 'Cannot find an online source')
        return

    auto  = ADDON.getSetting('DOWNLOAD_AUTO')
    index = GetLinkIndex(resolved, not auto)

    if index < 0:
        return

    url  = resolved[index][1]
    file = urllib.unquote_plus(url.rsplit('/')[-1])
    file = utils.fileSystemSafe(file)

    folder = ADDON.getSetting('DOWNLOAD_FOLDER')
    if len(folder) == 0:
        folder = 'special://profile/addon_data/plugin.video.watchcartoononline/downloads'

    import sfile

    if not sfile.exists(folder):
        sfile.makedirs(folder)

    file = os.path.join(folder, file)

    try:
        import download
        download.download(url, file, title)
    except Exception, e:
        print '%s - %s Error during downloading of %s' % (TITLE, VERSION, title)
        print str(e)



def PlayVideo(_url, select):
    resolved = resolve.ResolveURL(_url)

    if len(resolved) == 0:
        url = None
        msg = 'Unidentified Video Host'
    else:
        index = GetLinkIndex(resolved, select)

        if index == None:
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem(''))
            return

        resolver = resolved[index][0]
        url      = resolved[index][1]
        msg      = resolved[index][2]

    if url:
        url = url.split('"')[0]
        url = url.replace(' ', '%20')

    if not url:
        d   = xbmcgui.Dialog()
        d.ok(TITLE + ' - ' + VERSION, '', msg, '')

        print 'WATCHCARTOONSONLINE - (%s) Failed to locate video for %s' % (msg, _url)
        return

    html  = utils.getHTML(_url)
    image = common.parseDOM([x for x in re.compile('(<img.+?>)').findall(html) if "/thumb" in x], "img", ret="src")
    if image:
        image = image[0]
    else:
        image = ''
    title = common.parseDOM([x.decode('utf-8') for x in re.compile('(<a.+?</a>)').findall(html) if _url in x], "a")[0]
    title = utils.clean(title.encode('utf-8'))

    liz = xbmcgui.ListItem(title, iconImage=image, thumbnailImage=image)

    metaData = {'title': title}
    meta.GetMetaData(title, metaData)
    liz.setInfo( type='Video', infoLabels=metaData)

    liz.setProperty('IsPlayable','true')

    if int(sys.argv[1]) == -1:
        pl = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        pl.clear()
        pl.add(url, liz)
        #xbmc.Player().play(pl)

        player = XBMCPlayer(xbmc.PLAYER_CORE_DVDPLAYER)
        player.SetMetaData(metaData)
        player.play(pl)
        while player.is_active:
           xbmc.sleep(100)
    else:
        liz.setPath(url)
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, liz)
        

def AddEpisode(name, url, image=None):
    menu = []
    menu.append(('Download', 'XBMC.RunPlugin(%s?mode=%d&url=%s&title=%s)' % (sys.argv[0], DOWNLOAD, urllib.quote_plus(url), urllib.quote_plus(name))))
    if AUTOPLAY:
        menu.append(('Select video host', 'XBMC.RunPlugin(%s?mode=%d&url=%s)' % (sys.argv[0], HOST, urllib.quote_plus(url))))
    AddDir(name, EPISODE, url, image=image, isFolder=False, menu=menu)


def AddSeries(name, url):
    AddDir(name, SERIES, url)


def AddSection(name, image, url):
    if image == '':
        image = ICON
    else:
        image=os.path.join(ARTWORK, image+'.png')

    AddDir(name, SECTION, url, image, isFolder=True)


def AddDir(name, mode, url='', image=None, isFolder=True, page=1, keyword=None, infoLabels=None, menu=None):
    name = utils.clean(name)

    if not image:
        image = ICON

    u  = sys.argv[0] 
    u += '?mode='  + str(mode)
    u += '&title=' + urllib.quote_plus(name)
    u += '&image=' + urllib.quote_plus(image)
    u += '&page='  + str(page)

    if url != '':     
        u += '&url='   + urllib.quote_plus(url) 

    if keyword:
        u += '&keyword=' + urllib.quote_plus(keyword) 

    if infoLabels:
        infoLabels['title'] = name
    else:
        infoLabels = { 'title' : name }

    if mode == EPISODE:
        SetInfoData(name, infoLabels)
        if infoLabels['playcount'] == 1:
            menu.append(('Mark as unwatched', 'XBMC.RunPlugin(%s?mode=%d&url=%s&title=%s)' % (sys.argv[0], MARKUNWATCHED, urllib.quote_plus(url), urllib.quote_plus(name))))
        else:
            menu.append(('Mark as watched', 'XBMC.RunPlugin(%s?mode=%d&url=%s&title=%s)' % (sys.argv[0], MARKWATCHED, urllib.quote_plus(url), urllib.quote_plus(name))))
        
    liz = xbmcgui.ListItem(infoLabels['title'], iconImage=image, thumbnailImage=image)

    if menu:
        liz.addContextMenuItems(menu)


    liz.setInfo(type='Video', infoLabels=infoLabels)

    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=u, listitem=liz, isFolder=isFolder)


def SetInfoData(name, infoLabels):
    try:
        # Try to gather meta info
        meta.GetMetaData(name, infoLabels)

        # If an episode number is known then we can construct a better name
        if infoLabels['episode']:
            infoLabels['title'] = infoLabels['season'] + 'x' + infoLabels['episode'] + ': ' + infoLabels['episodeName']

        if meta.GetWatchedStatus(infoLabels) == True:
            infoLabels['overlay'] = 7
            infoLabels['playcount'] = 1
        else:
            infoLabels['overlay'] = 0
            infoLabels['playcount'] = 0
    except Exception, e:
            print 'WCO EXCEPTION: ' + str(e)
        

def get_params(path):
    params = {}
    path   = path.split('?', 1)[-1]
    pairs  = path.split('&')

    for pair in pairs:
        split = pair.split('=')
        if len(split) > 1:
            params[split[0]] = split[1]

    return params


params = get_params(sys.argv[2])

mode   = None
url    = None
title  = None


try:    mode = int(urllib.unquote_plus(params['mode']))
except: pass

try:    url = urllib.unquote_plus(params['url'])
except: pass

try:    title = urllib.unquote_plus(params['title'])
except: pass


if mode == SECTION:
    DoSection(url)

elif mode == SERIES:    
    html = utils.getHTML(url)

    while('Previous Entries' in html):
        DoSeries(html)
        url  = re.compile('<div class="alignleft"><a href="(.+?)".+?Previous Entries</a>').search(html).group(1)
        html = utils.getHTML(url)

    DoSeries(html)
    try:    xbmcplugin.addSortMethod(int(sys.argv[1]), xbmcplugin.SORT_METHOD_VIDEO_SORT_TITLE_IGNORE_THE)
    except: pass

elif mode == EPISODE:
    try:
        PlayVideo(url, (not AUTOPLAY))
    except Exception, e:
        print str(e)
        raise

elif mode == DOWNLOAD:
    try:
        DownloadVideo(url, title)
    except Exception, e:
        print str(e)
        raise

elif mode == HOST:
    selectHost(url)

elif (mode == MARKWATCHED) or (mode == MARKUNWATCHED):
    metaData = {}
    info = meta.GetMetaData(title, metaData)
    meta.SetWatchedStatus(metaData, mode == MARKWATCHED)
    xbmc.executebuiltin('XBMC.Container.Refresh')

elif mode == SEARCH:
    Search()

else:
    Main()

xbmcplugin.endOfDirectory(int(sys.argv[1]))