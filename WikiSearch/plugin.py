###
# Copyright (c) 2004,2008,2010 Grant Bowman
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

from supybot.commands import *

#import supybot

import re, time, socket, string, urllib, inspect
import urllib2, threading, HTMLParser, xml.dom.minidom

import supybot.dbi as dbi
import supybot.conf as conf
import supybot.utils as utils
import supybot.world as world
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks

filename = conf.supybot.directories.data.dirize('WikiSearch.db')



class WikiSearchDB(dbi.DB):
    Mapping = 'flat'

    class Record(dbi.Record):
        __fields__ = [
            'name',
            'type', # {'TwikiSite', 'KwikiSite', 'MoinSite', 'UsemodSite'}
            'autoLoad',
            'baseUrl',
            'indexUrl',
            'waitPeriod', # = 86400
            'announceChannels', # = []
            'announceMessage', # = 'Completed update of %s TWiki topic names.'
            'twikiEnd', # = 'WebTopicList?skin=plain'
            'webList', # [] for Twiki only
            ]

    def __init__(self, irc, *args, **kwargs):
        dbi.DB.__init__(self, irc, *args, **kwargs)

    def site(self, name, type, autoLoad, baseUrl, indexUrl, waitPeriod,
        announceChannels, announceMessage, twikiEnd='', webList=[]):
        n = self.Record(name=name, type=type, autoLoad=autoLoad,
            baseUrl=baseUrl, indexUrl=indexUrl, waitPeriod=waitPeriod,
            announceChannels=announceChannels, announceMessage=announceMessage,
            twikiEnd=twikiEnd, webList=webList)
        id = self.add(n)
        return id

    def getId(self, xName):
        for x in iter(self):
            if x.name == xName:
                return x.id

    def getValue(self, xName, xField):
        for x in iter(self):
            if x.name == xName:
                exec 'val = x.%s' % (xField)
                return val

    def getFieldNames(self):
        return self.Record.__fields__

    def announceAppend(self, xName, xChannel):
        for x in iter(self):
            if x.name == xName:
                x.announceChannels.append(xChannel)
                self.set(x.id, x)
                return True
        return False

    def announceRemove(self, xName, xChannel):
        for x in iter(self):
            if x.name == xName:
                if xChannel in x.announceChannels:
                    x.announceChannels.remove(xChannel)
                    self.set(x.id, x)
                    return True
                else:
                    return False


class WikiSearch(callbacks.Plugin):
    """ This plugin provides page/topic name searching and urls.  Page/topic names
    are collected from a wiki's site manually and/or scheduled.
    (daily by default) """
    threaded = True


    # To do - add thanks for the specific wiki parsers.
    # To do - add exception handling for calls to urllib2 & ClientCookie
    #         URLError: <urlopen error (-3, 'Temporary failure in name resolution')>
    #         HTTPError: HTTP Error 404: Not Found
    # To do - if a wiki doesn't parse, stop the failure condition for the
    #         configured wiki, especially for TWiki Webs.
    # To do - re-check help messages/user visible strings
    # To do - more use of 'raise callbacks.ArgumentError' in subobjects?
    # To do - for twiki.org's Main web - must provide username TWikiGuest password guest
    # To do - on add wiki, self.registryValue('defaultWiki') = the only wiki configured
    #         and add check for when removing wikis 2-1 (set defaultWiki)
    #         or 1-1 (clear defaultWiki)
    #         Q - for all channels?
    # To do - add to BaseSite.SiteUrl
    #             elif hits > 1:
    #                 the display of all hits.
    # To do - replace all self.cn with self.__class__.__name__
    # To do - using the 'inChannel' wrapper may not be the best way
    
    # future features - other wiki types (C2, Tavi, etc.)
    #                   see http://usemod.com/cgi-bin/mb.pl?AllPages
    #                   and http://usemod.com/cgi-bin/mb.pl?MetaWiki
    #
    # A supporting ctwoHTMLParser class could use either of two hard-coded urls.
    #
    #http://c2.com/cgi/wikiNames
    # or
    #http://sunir.org/apps/meta.pl?list=WikiWiki
    #
    # See http://c2.com/cgi/wiki?WikiList for more info.

    def __init__(self,irc):
        self.__parent = super(WikiSearch, self)
        self.__parent.__init__(irc)
        self.locks = {}
        self.firstCall = True # used by __call__ to give commands
                              # I had trouble calling from __init__
        self.db = WikiSearchDB(filename)
        self.cn = self.__class__.__name__
        self.wikiTypes = ['twiki','kwiki','moin','usemod', 'pmwiki',
        'tracwiki', 'phpwiki', 'zwiki']
        self.gettingLockLock = threading.Lock()

    #def foo(self, irc, msg, args): # for testing
    #    irc.reply(irc.irc.__class__)

    def die(self):
        """
        Called when closing down the WikiSearch plugin.
        """
        if self.db.flush in world.flushers:
            world.flushers.remove(self.db.flush)
        #for x in iter(self.db):
            #self.db.set(x.id, getattr(self, x.name).record)
        self.db.close()
        callbacks.Privmsg.die(self)

    def __call__(self, irc, msg): # adapted from RSS plugin
        """
        Automatically called every few seconds.  Handles all threading.
        """

        def _siteActions():
            """
            used to get a dictionary with key of site &
            data of channels to announce results.
            """
            actionSites = {}
            for site in iter(self.db):
                for channel in irc.state.channels:
                    #if channel in site.announceChannels:  # announced or not the sites should update
                    # if not announced then dailyUpdateHour doesn't apply
                    now = int(time.time())
                    myWait = int(site.waitPeriod)
                    try:
                        previous = int(getattr(self, site.name).updateTime)
                    except AttributeError:
                        # no self.site object, so don't announce at all
                        previous = now
                    #print myWait.__class__.__name__
                    #print now, previous, now-previous, int(myWait)
                    if self.registryValue('dailyUpdateHour'):
                        # can't use 0 for midnight daily update
                        currentHour = int(time.strftime('%H',
                                          time.localtime()))
                        if currentHour == \
                           self.registryValue('dailyUpdateHour') and \
                                               now - previous > 3600:
                            # timer not ready, but
                            # dailyUpdateHour matches and
                            # site hasn't updated during the last hour
                            actionSites.setdefault(site.name, []
                                                   ).append(channel)
                    elif now - previous > myWait:
                        # compare updateTime to waitPeriod
                        actionSites.setdefault(site.name, []
                                               ).append(channel)
                        #else: # timer not ready
            return actionSites

        callbacks.Privmsg.__call__(self, irc, msg)
        goAnnounceSites = _siteActions() # {site: [announce channels]}
        irc = callbacks.SimpleProxy(irc, msg)
        self.log.debug('WikiSearch.__call__ %s' % (goAnnounceSites))
        if self.firstCall: # run commands troublesome in __init__
            self.firstCall = False
            #self._addcommands(irc, msg, '') # commandAliases
            self._loadFromDb(irc, msg)      # load from data/Wiki.db
        else:
            for (siteName, channels) in goAnnounceSites.iteritems():
                self.log.debug('WikiSearch.__call__ site %s channels %s' % (
                    siteName, channels))
                # We check if we can acquire the lock right here because if we
                # don't, we'll possibly end up spawning a lot of threads to
                # update the site.  This thread may run for a number of
                # bytecodes before it switches to a thread that'll get the
                # lock in _newHeadlines.
                if self._acquireLock(siteName, blocking=False):
                    try:
                        t = threading.Thread(target=self._updating,
                                             name='Fetching <%s>' % siteName,
                                             args=(irc, siteName, channels))
                        self.log.debug('Spawning thread to fetch <%s>' % (
                            siteName))
                        world.threadsSpawned += 1
                        t.setDaemon(True)
                        t.start()
                    finally:
                        self._releaseLock(siteName)
                        time.sleep(0.1) # So other threads can run.

    def _updating(self, irc, site, channels): # adapted from RSS plugin
        """
        Used by __call__
        site is a record from self.db, channels is a list
        """
        try:
            # We acquire the lock here so there's only one announcement thread
            # in this code at any given time.  Otherwise, several announcement
            # threads will getFeed (all blocking, in turn); then they'll all
            # want to sent their news messages to the appropriate channels.
            # Note that we're allowed to acquire this lock twice within the
            # same thread because it's an RLock and not just a normal Lock.
            mySite = self.db.getValue(site, 'name')
            myAnnc = self.db.getValue(site, 'announceMessage')
            myChans = self.db.getValue(site, 'announceChannels')
            self._acquireLock(mySite, blocking=True)
            self.log.info('Updating %s' % (mySite))
            getattr(self, mySite)._siteUpdate(irc) # the work
            for channel in channels:
                self.log.debug('bingo - %s %s %s' % (mySite, channel,
                    myAnnc))
                if channel in myChans:
                    irc.reply(myAnnc, to=channel, prefixName=False, private=True)
        finally:
            self._releaseLock(mySite)

    def _acquireLock(self, wiki, blocking=True): # adapted from RSS plugin
        """
        Used by __call__
        """
        try:
            self.gettingLockLock.acquire()
            try:
                lock = self.locks[wiki]
            except KeyError:
                lock = threading.RLock()
                self.locks[wiki] = lock
            return lock.acquire(blocking=blocking)
        finally:
            self.gettingLockLock.release()

    def _releaseLock(self, wiki): # adapted from RSS plugin
        """
        Used by __call__
        """
        self.locks[wiki].release()

    def _loadFromDb(self, irc, msg):
        """
        Used by __call__ when self.firstCall == True
        """
        for x in iter(self.db): # iterates on the records themselves
            if x.autoLoad:
                #print x.id, x.name, x.type, x.autoLoad, x.baseUrl, \
                    #x.indexUrl, #x.waitPeriod, x.announceChannels, \
                    # x.announceMessage, x.twikiEnd, #x.webList
                if x.type == 'TwikiSite':
                    setattr(self, x.name, TwikiSite(self.log, self.db, x.id))
                    getattr(self, x.name).siteUpdate(irc)
                elif x.type == 'KwikiSite':
                    setattr(self, x.name, KwikiSite(self.log, self.db, x.id))
                    getattr(self, x.name).siteUpdate(irc)
                elif x.type == 'MoinSite':
                    setattr(self, x.name, MoinSite(self.log, self.db, x.id))
                    getattr(self, x.name).siteUpdate(irc)
                elif x.type == 'UsemodSite':
                    setattr(self, x.name, UsemodSite(self.log, self.db, x.id))
                    getattr(self, x.name).siteUpdate(irc)
                elif x.type == 'PmwikiSite':
                    setattr(self, x.name, PmwikiSite(self.log, self.db, x.id))
                    getattr(self, x.name).siteUpdate(irc)
                elif x.type == 'TracwikiSite':
                    setattr(self, x.name, TracwikiSite(self.log, self.db, x.id))
                    getattr(self, x.name).siteUpdate(irc)
                elif x.type == 'PhpwikiSite':
                    setattr(self, x.name, PhpwikiSite(self.log, self.db, x.id))
                    getattr(self, x.name).siteUpdate(irc)
                elif x.type == 'ZwikiSite':
                    setattr(self, x.name, ZwikiSite(self.log, self.db, x.id))
                    getattr(self, x.name).siteUpdate(irc)
                else:
                    irc.error('%s._loadFromDb invalid autoload type %s' % (
                    self.cn, x.type))
                    return

    #def _addcommands(self, irc, msg, args):
    #    """ Disabled
    #    Create command aliases.  A little fun.
    #    Used by __call__ when self.firstCall == True
    #    """
    #    # Startup timing of executing these commands is tricky since
    #    #     using __init__ seems to be too early to use any of the
    #    #     registry values.
    #
    #    # Commands are probably needed to add and remove items as well as
    #    #     add & remove the runtime bindings.  This capability might be
    #    #     better off provided in src/Misc or Owner.  A programmatic
    #    #     (rather than exclusively user) API to Alias would do the trick
    #    #     as well. Much discussion with the other developers would be
    #    #     required before proposing such a system.
    #    for alias in conf.supybot.plugins.Wiki.commandAliases():
    #        #exec 'self.%s = self.wiki' % (alias)
    #        setattr(self, alias, self.wiki)
    #        setattr(self, '%surl' % (alias), self.url)
    #        setattr(self, '%supdate' % (alias), self.update)
    #        setattr(self, '%sstatus' % (alias), self.status)
    #    #irc.replySuccess()

    def add(self, irc, msg, args, xName, xType, xBaseUrl, xIndexWeb):
        """<name> <Type> <base url> <index url | web list>
        
        Adds a wiki. Type must be one of Twiki, Kwiki, Moin, Usemod, Pmwiki,
        Trac Wiki or Php Wiki.  Index Url is used for all wikis except Twiki
        which uses a web list.  Default values for waitPeriod,
        announceChannels, announceMessage may be changed by editing
        data/Wiki.db.
        """
        #(xName, xType, xBaseUrl, xIndexWeb) = \
            #inspect.getArgs(args, required=4)
        #xName = xName.lower()
        if xName in self._siteList():
            irc.error('%s wiki not added, it already exists in data/WikiSearch.db.' % (
                xName), Raise=True)
            #raise callbacks.ArgumentError
        elif xName in self.wikiTypes:
            irc.error('%s wiki not added, name can not be any of %s.' % (
                xName, self.wikiTypes), Raise=True)
            #raise callbacks.ArgumentError
        if xType not in self.wikiTypes:
            irc.error('Wiki not added. Type must be one of %s.' % (
                utils.str.commaAndify(self.wikiTypes)))
            raise callbacks.ArgumentError
        self.log.debug('%s.add %s' % (self.cn,
            utils.str.commaAndify([xName, xType, xIndexWeb])))
        # xIndexWeb is a webList for Twiki and indexUrl for others
        # To do - sometimes remove trailing / or _urlString from xBaseUrl if present
        xAutoLoad = True
        xWaitPeriod = 86400 # 24 hours
        xAnnounceChannels = []
        if xType == 'twiki':
            xType = 'TwikiSite'
            xIndexWeb = xIndexWeb.split()
            xTwikiEnd = 'WebTopicList?skin=plain'
            xAnnounceMessage = 'Updated %s wiki.' % (xName)
            xId = self.db.site(xName, xType, xAutoLoad,
                xBaseUrl, '', xWaitPeriod, # '' is indexUrl
                xAnnounceChannels, xAnnounceMessage,
                xTwikiEnd, xIndexWeb)
            setattr(self, xName, TwikiSite(self.log, self.db,
                xId)) # instantiate Twiki
        elif xType == 'kwiki':
            xType = 'KwikiSite'
            xAnnounceMessage = 'Updated %s wiki.' % (xName)
            xId = self.db.site(xName, xType, xAutoLoad,
                xBaseUrl, xIndexWeb, xWaitPeriod,
                xAnnounceChannels, xAnnounceMessage)
            setattr(self, xName, KwikiSite(self.log, self.db,
                xId)) # instantiate Kwiki
        elif xType == 'moin':
            xType = 'MoinSite'
            xAnnounceMessage = 'Updated %s wiki.' % (xName)
            xId = self.db.site(xName, xType, xAutoLoad,
                xBaseUrl, xIndexWeb, xWaitPeriod,
                xAnnounceChannels, xAnnounceMessage)
            setattr(self, xName, MoinSite(self.log, self.db,
                xId)) # instantiate Moin
        elif xType == 'usemod':
            xType = 'UsemodSite'
            xAnnounceMessage = 'Updated %s wiki.' % (xName)
            xId = self.db.site(xName, xType, xAutoLoad,
                xBaseUrl, xIndexWeb, xWaitPeriod,
                xAnnounceChannels, xAnnounceMessage)
            setattr(self, xName, UsemodSite(self.log, self.db,
                xId)) # instantiate Usemod
        elif xType == 'pmwiki':
            xType = 'PmwikiSite'
            xAnnounceMessage = 'Updated %s wiki.' % (xName)
            xId = self.db.site(xName, xType, xAutoLoad,
                xBaseUrl, xIndexWeb, xWaitPeriod,
                xAnnounceChannels, xAnnounceMessage)
            setattr(self, xName, PmwikiSite(self.log, self.db,
                xId)) # instantiate PmWiki
        elif xType == 'tracwiki':
            xType = 'TracwikiSite'
            xAnnounceMessage = 'Updated %s wiki.' % (xName)
            xId = self.db.site(xName, xType, xAutoLoad,
                xBaseUrl, xIndexWeb, xWaitPeriod,
                xAnnounceChannels, xAnnounceMessage)
            setattr(self, xName, TracwikiSite(self.log, self.db,
                xId)) # instantiate Trac Wiki
        elif xType == 'phpwiki':
            xType = 'PhpwikiSite'
            xAnnounceMessage = 'Updated %s wiki.' % (xName)
            xId = self.db.site(xName, xType, xAutoLoad,
                xBaseUrl, xIndexWeb, xWaitPeriod,
                xAnnounceChannels, xAnnounceMessage)
            setattr(self, xName, PhpwikiSite(self.log, self.db,
                xId)) # instantiate Php Wiki
        elif xType == 'zwiki':
            xType = 'ZwikiSite'
            xAnnounceMessage = 'Updated %s wiki.' % (xName)
            xId = self.db.site(xName, xType, xAutoLoad,
                xBaseUrl, xIndexWeb, xWaitPeriod,
                xAnnounceChannels, xAnnounceMessage)
            setattr(self, xName, ZwikiSite(self.log, self.db,
                xId)) # instantiate Php Wiki
        else:
            irc.error('%s.add needs update for type %s' % (self.cn, xType))
            raise callbacks.ArgumentError
        # all
        getattr(self, xName).siteUpdate(irc)
    add = wrap(add, [additional('lowered'), additional('lowered'),
        additional('url'), rest('anything')])

    def _siteList(self):
        """
        Returns list of sites from the database
        """
        names = []
        for x in iter(self.db):
            names.append(x.name)
        return names

    def _replyListing(self, aString, aRecord, channel):
        """
        Returns a string of record values for replies.
        """
        if channel:
            xBold = self.registryValue('bold', channel)
        else:
            xBold = False
        for xField in self.db.getFieldNames():
            if xBold:
                aString += '%s:%s ' % (ircutils.bold(xField),
                    getattr(aRecord, xField))
            else:
                aString += '%s:%s ' % (xField,
                    getattr(aRecord, xField))
        return aString

    def detail(self, irc, msg, args, xChannel, xName):
        """<name>

        Gives the full details about a wiki from the database.
        """
        #xName = inspect.getArgs(args, required=1)
        xId = self.db.getId(xName)
        if xId:
            xRecord = getattr(self, xName).record
            s = 'WikiSearch details - '
            s = self._replyListing(s, xRecord, xChannel)
            irc.reply(s)
        else:
            irc.reply('Wiki %s not found.' % (xName))
    detail = wrap(detail, ['inChannel', additional('lowered')])

    def remove(self, irc, msg, args, xChannel, xName):
        """<name>

        Removes a wiki from the database.
        """
        #xName = inspect.getArgs(args, required=1)
        xId = self.db.getId(xName)
        if xId:
            try:
                xRecord = getattr(self, xName).record
                delattr(self, xName)
            except:
                print 'error';
            self.db.remove(xId)
            self.db.flush()
            s = 'WikiSearch wiki removed - '
            s = self._replyListing(s, xRecord, xChannel)
            irc.reply(s)
        else:
            irc.reply('Wiki %s not found.' % (xName))
    remove = wrap(remove, ['inChannel', additional('lowered')])

    def list(self, irc, msg, args, xChannel, xName):
        """[<name>]

        Lists information about a wiki.  Defaults to listing the names of all
        known wikis.
        """
        #xName = inspect.getArgs(args, required=0, optional=1)
        xId = self.db.getId(xName)
        if xId:
            xRecord = getattr(self, xName).record # canonical
            #self.db.get(xId) # should match
            s = 'WikiSearch - '
            s = self._replyListing(s, xRecord, xChannel)
            irc.reply(s)
        else:
            if len(self._siteList()):
                irc.reply('WikiSearch wikis - %s' % (utils.str.commaAndify(
                    self._siteList())))
            else:
                irc.reply('WikiSearch - no wikis configured')
    list = wrap(list, ['inChannel', optional('lowered')])

    def status(self, irc, msg, args, goodSite):
        """[<wiki>]

        Allows users to know when the page/topic name storage was last
        updated.  Default is for all wikis.
        """
        def _statusCall(site):
            #try:
            getattr(self, site).siteStatus(irc)
            #except: # To do - be more specific about exception handling
                #irc.error('%s, what %s?  Try an update first.' % (site, site))
                ## no return
        #goodSite = inspect.getArgs(args, required=0, optional=1)
        #goodSite = goodSite.lower() # now goodSite = [<wiki>]
        currentSites = self._siteList()
        if len(currentSites) == 0:
            irc.error('No WikiSearch wikis configured.')
            raise callbacks.ArgumentError
        elif len(currentSites) == 1:
            self.log.debug('%s.status only 1 site configured' % (self.cn))
            _statusCall(currentSites[0]) # ignores goodSite
        elif goodSite in currentSites:
            self.log.debug('%s.status passed %s' % (self.cn, goodSite))
            _statusCall(goodSite)
        else:
            self.log.debug('%s.status scan' % (self.cn))
            map(_statusCall, currentSites)
    status = wrap(status, [optional('lowered')])

    def announce(self, irc, msg, args, xWiki, xChannel):
        """<wiki> [[-]<channel>]
    
        Checks and sets a wiki's list of announce channels used
        during automated updates. Use a -<channel> to remove one.
        <wiki> must already be added and bot must already be joined
        to <channel>.
        """
        # editing of data/Wiki.db by hand no longer required
        #(xWiki, xChannel) = inspect.getArgs(args, required=1, optional=1)
        #xWiki = xWiki.lower() # [<wiki>]
        if not xWiki in self._siteList():
            irc.error('%s wiki is not valid.' % (xWiki), Raise=True)
            #raise callbacks.ArgumentError
        if xChannel:
            AddFlag = True
            if xChannel[0] == '-':
                xChannel = xChannel[1:]
                AddFlag = False
            elif xChannel[0] == '+':
                xChannel = xChannel[1:]
            # ready now
            if xChannel in irc.state.channels:
                if AddFlag:
                    self.db.announceAppend(xWiki, xChannel)
                    irc.replySuccess()
                else:
                    if self.db.announceRemove(xWiki, xChannel):
                        irc.replySuccess()
                        return
                    else:
                        irc.error('Channel %s not in announce list for %s.'%(
                            xChannel, xWiki), Raise=True)
                        #raise callbacks.ArgumentError
            else:
                irc.error('%s is not joined to channel %s.' % (irc.irc.nick,
                                                               xChannel), Raise=True)
                #raise callbacks.ArgumentError
        else:
            xList = self.db.getValue(xWiki, 'announceChannels')
            if xList:
                irc.reply('%s announce channels: %s' % (xWiki, xList))
            else:
                irc.reply('%s announce channels: %s' % (xWiki, '<none configured>'))
    announce = wrap(announce, [additional('lowered'), optional('text')])

    def update(self, irc, msg, args, goodSite):
        """[<wiki>]

        Updates WikiSearch page/topic names, default is for all wikis.
        """
        def _updateCall(xSite):
            try:
                getattr(self, xSite).siteUpdate(irc)
            except: # To do - be more specific about exception handling
                self.log.debug('%s._updateCall instantiating %s' % (
                    self.cn, xSite))
                xId = self.db.getId(xSite)
                xType = self.db.getValue(xSite, 'type')
                #setattr(self, xSite, TwikiSite(self.log, self.db, xId))
                if xType == 'TwikiSite':
                    setattr(self, xSite, TwikiSite(self.log, self.db, xId))
                    getattr(self, xSite).siteUpdate(irc)
                elif xType == 'KwikiSite':
                    setattr(self, xSite, KwikiSite(self.log, self.db, xId))
                    getattr(self, xSite).siteUpdate(irc)
                elif xType == 'MoinSite':
                    setattr(self, xSite, MoinSite(self.log, self.db, xId))
                    getattr(self, xSite).siteUpdate(irc)
                elif xType == 'UsemodSite':
                    setattr(self, xSite, UsemodSite(self.log, self.db, xId))
                    getattr(self, xSite).siteUpdate(irc)
                elif xType == 'PmwikiSite':
                    setattr(self, xSite, PmwikiSite(self.log, self.db, xId))
                    getattr(self, xSite).siteUpdate(irc)
                elif xType == 'TracwikiSite':
                    setattr(self, xSite, TracwikiSite(self.log, self.db, xId))
                    getattr(self, xSite).siteUpdate(irc)
                elif xType == 'PhpwikiSite':
                    setattr(self, xSite, PhpwikiSite(self.log, self.db, xId))
                    getattr(self, xSite).siteUpdate(irc)
                elif xType == 'ZwikiSite':
                    setattr(self, xSite, ZwikiSite(self.log, self.db, xId))
                    getattr(self, xSite).siteUpdate(irc)
                else:
                    irc.error('%s._loadFromDb invalid autoload type %s' % (
                    self.cn, xType))
                    return

                    # Future feature - pickle objects & restore from disk.
                    #                  This will be helpful when the Wiki
                    #                  being scanned is unavailable or
                    #                  network routing issues exist.
                getattr(self, xSite).siteUpdate(irc)
                # no return
        #goodSite = inspect.getArgs(args, required=0, optional=1)
        #goodSite = goodSite.lower() # [<wiki>]
        currentSites = self._siteList()
        if len(currentSites) == 0:
            irc.error('No WikiSearch wikis configured.')
            return
        elif len(currentSites) == 1: # ignores goodSite
            # To do - and not goodSite
            self.log.debug('%s.update only 1 site configured, %s' % (
                           self.cn, currentSites[0]))
            _updateCall(currentSites[0])
        elif goodSite in currentSites:
            self.log.debug('%s.update passed %s' % (self.cn, goodSite))
            _updateCall(goodSite)
        else:
            self.log.debug('%s.update scan' % (self.cn))
            map(_updateCall, currentSites)
    update = wrap(update, [optional('lowered')])
    # must be owner to use update? [('checkCapability', 'owner') ...]
            
    def url(self, irc, msg, args, words):
        """[<wiki>] [<web>] [<page name>]

        Returns a url given a *specific* page/topic name, case insensitive.
        If no <wiki> is given and the channel's defaultWiki is used (if set),
        otherwise all configured wikis are searched.  If no page/topic name is
        given, the wiki's URL is returned.  Only TWiki wikis have <webs>.
        """
        def _urlCall(xSite):
            #try:
                getattr(self, xSite).siteUrl(irc, msg, args)
            #except: # To do - be more specific about exception handling
                #irc.error('%s, what %s?  Try an update first.' % (site, site))
                # no return
        goodSite = ''
        currentSites = self._siteList()
        if irc.isChannel(msg.args[0]):
            channel = inspect.getChannel(msg, args)
            xDefaultWiki = self.registryValue('defaultWiki', channel)
        else:
            channel = ''
            xDefaultWiki = ''
        try:
            if len(args) > 1 and args[0].lower() in currentSites:
                goodSite = args.pop(0).lower()
                # to do - add checks for very slight chance of no site
                #         passed in and args[0] (web or topicname) = <wiki>
                #         therefore too few arguments.
        except IndexError: # no arguments passed in
            raise callbacks.ArgumentError
        # [<wiki>] stripped out
        if len(args) == 0 or len(args) > 2:
            raise callbacks.ArgumentError
        # goodSite = [<wiki>]   and   args = [[<web>], <topicname>]
        if len(currentSites) == 0:
            irc.error('No WikiSearch wikis configured.')
            raise callbacks.ArgumentError
        elif len(currentSites) == 1:
            self.log.debug('%s.url only 1 site configured' % (self.cn))
            _urlCall(currentSites[0]) # ignores goodSite
        elif goodSite in currentSites:
            self.log.debug('%s.url passed %s' % (self.cn, goodSite))
            _urlCall(goodSite)
        elif xDefaultWiki in currentSites:
            self.log.debug('%s.url default %s' % (self.cn, xDefaultWiki))
            _urlCall(xDefaultWiki)
        else:
            self.log.debug('%s.url scan' % (self.cn))
            map(_urlCall, currentSites)
    url = wrap(url, [many('something')])

    def search(self, irc, msg, args, words):
        """[<wiki>] [<web>] <regex>

        Returns all page/topic *names* that match, case insensitive.  If no
        site is given and the defaultWiki registry item is set, that value is
        used for [<wiki>].  Only TWiki wikis have webs.
        """
        def _wikiCall(xSite):
            #try:
                getattr(self, xSite).siteWiki(irc, msg, words)
            #except: # To do - be more specific about exception handling
                #irc.error('%s, what %s?  Try an update first.' % (site, site))
                # no return
        goodSite = ''
        currentSites = self._siteList()
        if words[0] in currentSites:
            goodSite = words[0]
            words = words[1:-1]
        elif ircutils.isChannel(msg.args[0]):
            goodSite = self.registryValue('defaultWiki', msg.args[0]) # inspect.getChannel(msg, args)
                # very slight chance of no site passed in and
                #     args[0] (web or regex) = site
            if not goodSite:
                raise callbacks.ArgumentError
        # <wiki> set in goodSite
        if len(words) == 0 or len(words) > 2:
            raise callbacks.ArgumentError
        # goodSite = [<wiki>]   and   words = [[<web>], <regex>]
        if len(currentSites) == 0:
            irc.error('No WikiSearch wikis configured.')
            raise callbacks.ArgumentError
        elif len(currentSites) == 1:
            self.log.debug('%s only 1 site configured' % (self.cn))
            _wikiCall(currentSites[0]) # ignores goodSite
        elif goodSite in currentSites:
            self.log.debug('%s passed %s' % (self.cn, goodSite))
            _wikiCall(goodSite)
        else:
            raise callbacks.ArgumentError
            # used to allow default search of all wikis - not any more.
            #self.log.debug('%s scan' % (self.cn))
            #map(_wikiCall, currentSites)
    search = wrap(search, [many('something')])

Class = WikiSearch


##########
##########
##########

class BaseSite(object):
    """
    Mixin for all Wiki.py *Site classes.
    """
    def __init__ (self, log, db, id):
        self.db = db
        self.id = id
        self.log = log
        self.updateTime = 0
        self._firstrun = True
        self.cn = self.__class__.__name__
        self.record = self.db.get(self.id)
        self.name = self.record.name
        self.log.info('%s.__init__ %s %s' % (self.cn, self.id, self.name))
        # self.firstSiteUpdate(irc) # can't do without an irc object

    def _siteUpdate(self, irc):
        """
        workhorse method used by update and __call__
        """
        #if self._firstrun:
        #    self._firstrun = False
        #    self.log.debug('%s._siteUpdate beginning first update '
        #        'of %s site.' % (self.cn, self.name))
        #    self.firstSiteUpdate(irc) # instantiate
        #else:
        y = irc.getCallback('WikiSearch').registryValue('timeout')
        try:
            getattr(self, self.name).updateTopics(y)
        except:
            self.log.debug('%s._siteUpdate getattr exception' % (
                self.cn))
            # tricky exec
            exec 'setattr(self, self.name, %s(self.name, '\
                 'self.record.indexUrl, self.record.baseUrl, self.log, %s))' % (self._parser, y)
        self.log.debug('%s._siteUpdate completed update '
            'of %s site.' % (self.cn, self.name))
        self.updateTime = time.time()

    def firstSiteUpdate(self, irc):
        """
        Instantiate single object
        """
        if not self.record.indexUrl:
            irc.error('%s.firstSiteUpdate - missing value for '
            'indexUrl.' % (self.cn), Raise=True)
            return
        y = irc.getCallback('WikiSearch').registryValue('timeout')
        # tricky exec
        exec 'setattr(self, self.name, %s(self.record.name, '\
             'self.record.indexUrl, self.record.baseUrl, self.log, %s))' % (self._parser, y)
        self.log.debug('%s.firstSiteUpdate completed first update '
            'of %s.' % (self.cn, self.name))
        self.updateTime = time.time()

    def siteUpdate(self, irc):
        """
        Performs the work of the update command.
        Calls the parser object's .updateTopics() method.
        """
        self._siteUpdate(irc)
        self.log.debug('%s.siteUpdate completed update '
            'of %s site.' % (self.cn, self.name))
        irc.reply(self.record.announceMessage)

    def siteWiki(self, irc, msg, args):
        """<regex>

        Returns all page/topic names that match.
        """
        if len(args) == 0:
            irc.reply('Please provide a search string.')
        else:
            term = args[0]
            (hits, result) = getattr(self, self.name).search(term)
            returnvalue = '(%s) %s: %s' % (str(hits),
                'hits', utils.str.commaAndify(result))
            if not hits:
                irc.reply('No %s pages are available for '
                    'search string: %s' % (self.name, term))
            elif hits:
                irc.reply(returnvalue)

    def siteStatus(self, irc):
        """
        Replies directly to users with page/topic name storage
        & last update time.
        """
        xBytes = getattr(self, self.name).bytes
        xDate = time.strftime('%Y-%m-%d T %H:%M (%Z), %A',
            time.localtime(getattr(self, self.name).updateTime))
        xTopics = len(getattr(self, self.name).topics)
        if xBytes < 1024:
            xKbString = '< 1'
        else:
            xKbString = str(xBytes/1024)
        # tricky - note the self._shortName
        irc.reply('%s %s %s Total of %s pages using %s kb RAM, valid as of %s.'%(
            self.name, self._shortName, self.record.baseUrl, xTopics,
            xKbString, xDate))

    def siteUrl(self, irc, msg, args):
        """[<topic name>]

        Returns a url given a specific page/topic name.
        """
        xBaseUrl = self.record.baseUrl
        if len(args) > 1:
            raise callbacks.ArgumentError
        elif len(args) == 0:
            irc.reply(xBaseUrl) # just the plain url
            return
        xTerm = args[0]
        (hits, result) = getattr(self, self.name).match(xTerm)
        if hits == 0:
            irc.reply("No %s pages found for %s.  Unverified: %s/%s" % (
                      self.name, xTerm, xBaseUrl, urllib.quote(xTerm)))
        elif hits == 1:
            # tricky - note the self._urlString
            irc.reply('%s%s%s' % (xBaseUrl, self._urlString,
                      urllib.quote(result[0])))
        elif hits > 1:
            irc.reply("Multiple (%s) pages found on %s wiki for %s." % (
                hits, self.name, xTerm))


class BaseParser(object):
    """
    Mixin for all Wiki.py *HTMLParser classes
    """
    # future feature - parse & allow search of author & date data if provided
    def __init__(self, name, url, baseUrl, log, updateTimeout):
        self.log = log
        self.url = url
        self.bytes = 0
        self.name = name
        self.topics = []
        self.updateTime = 0
        self.baseUrl = baseUrl
        # I'm astounded that #python folks say I can't
        # access the instance's "object reference name" in any way!
        # so I passed the name in and set it myself
        self.cn = self.__class__.__name__
        self.log.info('%s.__init__ %s %s' % (self.cn, self.name, self.url))

        # timeout is used once and thrown away
        self.updateTopics(updateTimeout)
        self.log.info('%s updated.' % (self.name))

    def updateTopics(self, updateTimeout):
        self.log.debug('%s.updatetopics start updating '
            'topic names from %s' % (self.cn, self.url))
        self.bytes = 0
        self.topics = []
        x = socket.getdefaulttimeout()
        socket.setdefaulttimeout(updateTimeout)
        #try:
        xLocalHtml = urllib2.urlopen(self.url)
        #except timeout:
        socket.setdefaulttimeout(x)
        for line in xLocalHtml.readlines():
            #print line
            self.feed(line)                  # assumes HTMLParser.HTMLParser
        self.log.debug('%s.updatetopics completed updating '
            'topic names from %s' % (self.cn, self.url))
        self.updateTime = time.time()
    
    def search(self, term):
        """
        Substring regex search.
        """
        result = []
        xSearch = re.compile(term, re.IGNORECASE)
        for topic in self.topics:
            if xSearch.search(topic):
                result.append(topic)
        if len(result):
            return (len(result), result)
        else:
            return (0, result)

    def match(self, term):
        """
        Use search.match instead of search.search, otherwise this is
        identical to above.  This will only match a /^term$/.
        """
        result = []
        xSearch = re.compile('^%s$' % (term), re.IGNORECASE)
        for topic in self.topics:
            if xSearch.match(topic):
                result.append(topic)
        if len(result):
            return (len(result), result)
        else:
            return (0, result)

##########


# A supporting class, one instance used per TWiki site

class TwikiSite(BaseSite):
    """
    TWiki code and web handling.

    An example TWiki URL to fetch topic names looks like this:
    http://wiki.example.com/twiki/bin/view/TWiki/WebTopicList?skin=plain

    @wikisearch add example twiki http://wiki.example.com/twiki/bin/view Main TWiki Sandbox

    The list of "TWiki webs" is customized during installation of each TWiki
    site.  A TWiki web functions as an administrative and topic name
    namespace.
    """
    # Due to complexity of TWiki having multiple webs/namespaces
    # many of the BaseSite methods are over-ridden and not used.
    def __init__ (self, log, db, id):
        BaseSite.__init__(self, log, db, id)
        self._parser = 'twikiHTMLParser'
        #self._shortName = 'Twiki'    # not used by TWiki code
        self._urlString = '/'
        # self.firstSiteUpdate(irc) # can't do without irc object

    def firstSiteUpdate(self, irc):
        """
        Instantiate objects, one for each TWiki web
        """
        # overrides BaseSite.firstSiteUpdate()
        if not self.record.webList:
            irc.error('%s.firstSiteUpdate - missing '
            'value for webList.' % (self.cn), Raise=True)
            return
            #raise callbacks.ArgumentError # ? ok to use in subobject?
        if not self.record.baseUrl:
            irc.error('%s.firstSiteUpdate - missing '
            'value for baseUrl.' % (self.cn), Raise=True)
            return
        if not self.record.twikiEnd:
            irc.error('%s.firstSiteUpdate - missing '
            'value for twikiEnd.' % (self.cn), Raise=True)
            return
        for web in self.record.webList:
            try:
                setattr(self, web, twikiHTMLParser(web, '%s%s%s%s%s' % (
                    self.record.baseUrl, self._urlString, web,
                    self._urlString, self.record.twikiEnd),
                    self.record.baseUrl, self.log))
                self.log.debug('%s.firstSiteUpdate completed first '
                    'update of %s web.' % (self.cn, web))
                self.updateTime = time.time()
            except:
                # To do - print traceback and/or be more specific
                # on exception type handling.
                irc.error('Wiki - TWiki retrieval of %s '
                    'topic list failed. It is unavailable.' % (web))
                self.updateTime = 0
                return
                # commented .remove to prevent it from disappearing
                #     from .conf file.  Explore Default value saving vs.
                #     run-time value saving
                #conf.supybot.plugins.Wiki.site1.webList().remove(web)
                #getattr(self.record, webList).remove(web) ?
                #
                # with tellbot, if list of webs was long, only 4 are allowed
                #     to time-out and the rest are skipped. I need to check
                #     where the timer is, set it lower, then find which code
                #     is timing out.  Alternative is to use a thread?

    def _siteUpdate(self, irc):
        """
        workhorse method used by update and __call__
        """
        # overrides BaseSite._siteUpdate()
        #if self._firstrun == True:
        #    self._firstrun = False
        #    self.log.debug('%s._siteUpdate beginning first update of '
        #        '%s site.' % (self.cn, self.name))
        #    # instantiate objects, one per TWiki web.
        #    self.firstSiteUpdate(irc)
        #else:
        for web in self.record.webList:
            y = irc.getCallback('WikiSearch').registryValue('timeout')
            try:
                getattr(self, web).updateTopics(y)
            except:
                self.log.debug('%s._siteUpdate getattr exception of'
                    '%s web.' % (self.cn, web))
                setattr(self, web, twikiHTMLParser(web, '%s%s%s%s%s' % (
                    self.record.baseUrl, self._urlString, web,
                    self._urlString, self.record.twikiEnd),
                    self.record.baseUrl, self.log, y))
            self.log.debug('%s._siteUpdate completed update of '
                '%s web.' % (self.cn, web))
        self.updateTime = time.time()

    def siteStatus(self, irc):
        """
        Replies directly to users with topic name storage & last update time.
        """
        # overrides BaseSite.siteStatus()
        xBytes = 0
        xTopics = 0
        xWebList = []
        xDate = time.strftime('%Y-%m-%d T %H:%M (%Z), %A',
            time.localtime(self.updateTime))
        for web in self.record.webList:
            xBytes = xBytes + getattr(self, web).bytes
            xTopics = xTopics + len(getattr(self, web).topics)
            xWebList.append(web)
        xKb = xBytes/1024
        if xBytes < 1024:
            xKbString = '< 1'
        else:
            xKbString = str(xBytes/1024)
        irc.reply('%s TWiki webs %s from %s  Total of %s topics using %s kb RAM, '
            'valid as of %s.' % (
            self.name, utils.str.commaAndify(xWebList), self.record.baseUrl,
            xTopics, xKbString, xDate))

    def siteUrl(self, irc, msg, args):
        """<web> [<topicname>]

        Returns a url given a specific topic name.
        """
        # overrides BaseSite.siteUrl()
        changed = False
        xBaseUrl = self.record.baseUrl
        if len(args) == 2:
            web = args[0]
            # validate passed-in web
            if web not in self.record.webList:
                xSearch = re.compile(web, re.IGNORECASE)
                for xWeb in self.record.webList:
                    if xSearch.search(xWeb):
                        changed = True
                        web = xWeb
                if not changed:
                    irc.reply('%s has no %s web' % (self.name, web))
                    return
            term = args[1]
            try:
                (hits, result) = getattr(self, web).match(term)
                returnvalue = '%s%s%s%s%s' % ( xBaseUrl, self._urlString, 
                               web, self._urlString, result[0])
                irc.reply(returnvalue)
            except:
                irc.reply("No %s topics found for %s.  Unverified: %s%s%s%s%s"%(
                                              web, term, xBaseUrl,
                                              self._urlString, web,
                                              self._urlString, term))
        elif len(args) == 1:
            term = args[0]
            anyresult = False
            for web in self.record.webList:
                (hits, result) = getattr(self, web).match(term)
                if hits == 1:
                    returnvalue = '%s%s%s%s%s' % ( xBaseUrl, self._urlString,
                                               web, self._urlString, result[0])
                    irc.reply(returnvalue)
                    anyresult = True
                elif hits > 1:
                    anyresult = True
                    irc.reply("Multiple (%s) topics found in %s web for %s."%(
                        hits, web, term))
            if not anyresult:
                irc.reply("No %s topics found for %s.  Unverified: %s%s%s%s%s"%(
                                              self.name, term, xBaseUrl,
                                              self._urlString,
                                              self.record.webList[0],
                                              self._urlString, term))
        elif len(args) == 0:
            # return first listed web's base url
            returnvalue ='%s%s%s%s' %(xBaseUrl, self._urlString,
                                    self.record.webList[0], self._urlString)
            irc.reply(returnvalue)
        else:
            irc.error('error - fell through in %s.wikiUrl' % (self.cn))
            return

    def siteWiki(self, irc, msg, args):
        """[<web>] <regex>

        Returns all topic names that match.
        """
        # overrides BaseSite.siteWiki()
        changed = False
        anyresult = False
        anylongresult = False
        if len(args) == 0:
            irc.reply('Please provide a search string.')
        elif len(args) > 2:
            irc.reply('Too many arguments.')
        else:
            xWeblist = self.record.webList
            if len(args) == 2:
                term = args[1]
                xWeblist = [args[0]]
                # validate passed-in web
                if args[0] not in self.record.webList:
                    xSearch = re.compile(args[0], re.IGNORECASE)
                    for xWeb in self.record.webList:
                        if xSearch.search(xWeb):
                            changed = True
                            xWeblist = [xWeb]
                    if not changed:
                        irc.reply('%s has no %s web' % (self.name, args[0]))
                        return
            elif len(args) == 1:
                term = args[0]
            else:
                irc.error('how did I get here?')
                return
            for web in xWeblist:
                (hits, result) = getattr(self, web).search(term)
                returnvalue = '%s (%s) %s: %s' % (
                    getattr(self, web).name, str(hits),
                        'hits', utils.str.commaAndify(result))
                if hits:
                    irc.reply(returnvalue)
                    anyresult = True
                if len(returnvalue) > 200: # To do - check 200 char limit
                    anylongresult = True
            if anylongresult:
                irc.reply('To see additional hits from a particular web, use'
                    ' the "wiki search <web> %s" command' % (term))
            if not anyresult:
                irc.reply( 'No %s topics are available for ' \
                    'search string: %s' % (self.name, term))


# A supporting class, one instance used per TWiki * web *

class twikiHTMLParser(HTMLParser.HTMLParser, BaseParser):
    """
    Parses TWiki WebTopicList?skin=plain HTML page for topic names.
    
    The parser depends on using this particular auto-generated result page.
    Changes to this will require changes to the parser.
    """
    def __init__(self, name, url, baseUrl, log, updateTimeout):
        HTMLParser.HTMLParser.__init__(self)
        BaseParser.__init__(self, name, url, baseUrl, log, updateTimeout)
    
    def handle_starttag(self, tag, attribs):
        """
        Over-rides HTMLParser method, get topic names from anchors
        """
        if tag == 'a':
            for tuple in attribs:
                # To do - don't grab the header & footer links
                if tuple[0] == 'href':
                    newtopicname = string.split( tuple[1], '/' )[-1]
                    self.topics.append(newtopicname)
                    self.bytes = self.bytes + len(newtopicname)
    
    #BaseParser.updateTopics(self, updateTimeout)

# one instance used per Kwiki site

class KwikiSite(BaseSite):
    """
    Kwiki code and site handling.
    
    @wikisearch add example kwiki http://www.example.com http://www.example.com/?action=search
    """
    def __init__ (self, log, db, id):
        BaseSite.__init__(self, log, db, id)
        self._parser = 'kwikiHTMLParser'
        self._shortName = 'Kwiki'
        self._urlString = '?'


# one instance used per Kwiki site

class kwikiHTMLParser(HTMLParser.HTMLParser, BaseParser):
    """
    Parses Kwiki blank search string result HTML page for page/topic names.
    
    The parser depends on using this particular auto-generated result page.
    Changes to this will require changes to the parser.
    """
    def __init__(self, name, url, baseUrl, log, updateTimeout):
        HTMLParser.HTMLParser.__init__(self)
        self.ina = False
        self.inClass = False
        BaseParser.__init__(self, name, url, baseUrl, log, updateTimeout)

    def updateTopics(self, updateTimeout):
        # overrides BaseParser.updateTopics()
        self.log.debug('%s.updatetopics start updating '
            'topic names from %s' % (self.cn, self.url))
        self.bytes = 0
        self.topics = []
        try: # ClientCookie required for parsing SocialText Kwikis
            import ClientCookie
            x = socket.getdefaulttimeout()
            socket.setdefaulttimeout(updateTimeout)
            #try:
            xLocalHtml = ClientCookie.urlopen(self.url)
            #except timeout:
        except: # To do - specify more specific exception
            x = socket.getdefaulttimeout()
            socket.setdefaulttimeout(updateTimeout)
            #try:
            xLocalHtml = urllib2.urlopen(self.url)
            #except timeout:
        socket.setdefaulttimeout(x)
        for line in xLocalHtml.readlines():
            self.feed(line)
        self.log.debug('%s.updatetopics completed updating '
            'topic names from %s' % (self.cn, self.url))
        self.updateTime = time.time()

    def handle_starttag(self, tag, attribs):
        """
        Over-rides HTMLParser method, sets self.ina and self.inClass.
        """
        if tag == 'td':
            for tuple in attribs:
                if tuple[0] == 'class' and (tuple[1] == 'page_name' or
                                            tuple[1] == 'page_id'):
                    # kwiki cases
                    self.inClass = True
        elif tag == 'a':
                for tuple in attribs:
                    #print tuple
                    if tuple[0] == 'class' and tuple[1] == 'list_page':
                        # socialtext
                        self.inClass = True
                        self.ina = True
                    if tuple[0] == 'href':
                        # kwiki
                        self.ina = True

    def handle_data(self, data):
        """
        Over-rides HTMLParser method
        """
        #print 'outside %s' % data
        #print data
        if self.ina and self.inClass:
            #print '                                      inside %s' % data
            self.topics.append(data)
            self.bytes = self.bytes + len(data)
        elif 'Cookies Required' in data:
            print 'ERROR - SocialText Workspace requires Cookies.'
            print 'ERROR - ClientCookie library is required for parsing ' \
                  'SocialText Workspace Kwikis'

    def handle_endtag(self, tag):
        """
        Over-rides HTMLParser method, clears self.ina and self.inClass.
        """
        if tag == 'td':
            self.inClass = False
        elif tag == 'a':
            self.ina = False
    

# one instance used per Moin site

class MoinSite(BaseSite):
    """
    Moin code and site handling.
    
    @wikisearch add example moin http://www.example.com http://www.example.com/TitleIndex?action=titleindex&mimetype=text/xml
    """
    def __init__ (self, log, db, id):
        BaseSite.__init__(self, log, db, id)
        self._parser = 'moinHTMLParser'
        self._shortName = 'Moin'
        self._urlString = '/'


# one instance used per Moin site

class moinHTMLParser(BaseParser):
    """
    Parses Moin TitleIndex XML for page/topic names.
    
    The parser depends on using this particular auto-generated result page.
    Changes to this will require changes to the parser.
    """
    def __init__(self, name, url, baseUrl, log, updateTimeout):
        BaseParser.__init__(self, name, url, baseUrl, log, updateTimeout)
    
    def updateTopics(self, updateTimeout):
        # overrides BaseParser.updateTopics()
        def _getText(element, tagname):
            result   = u''
            nodelist = element.getElementsByTagName(tagname)

            if nodelist <> None:
                for node in nodelist[0].childNodes:
                    if node.nodeType == node.TEXT_NODE:
                        result = result + node.data
            return result
        self.log.debug('%s.updatetopics start updating '
            'topic names from %s' % (self.cn, self.url))
        self.bytes = 0
        self.topics = []
        x = socket.getdefaulttimeout()
        socket.setdefaulttimeout(updateTimeout)
        #try:
        xTemp = urllib2.urlopen(self.url)
        #except timeout:
        socket.setdefaulttimeout(x)
        # watch for exceptions
        self.dom = xml.dom.minidom.parse(xTemp)
        for title in self.dom.getElementsByTagName('Title'):
            newtopic = title.childNodes[0].data
            self.bytes += len(newtopic)
            self.topics.append(newtopic)
        self.dom.unlink()
        # watch for exceptions
        self.log.debug('%s.updatetopics completed updating '
            'topic names from %s' % (self.cn, self.url))
        self.updateTime = time.time()
    

# one instance used per Usemod site

class UsemodSite(BaseSite):
    """
    Usemod code and site handling.
    
    @wikisearch add example usemod http://www.example.com/wiki.pl http://www.example.com/wiki.pl?action=index
    """
    def __init__ (self, log, db, id): # identical to TwikiSite
        BaseSite.__init__(self, log, db, id)
        self._parser = 'usemodHTMLParser'
        self._shortName = 'Usemod'
        self._urlString = '?'


# one instance used per Usemod site

class usemodHTMLParser(HTMLParser.HTMLParser, BaseParser):
    """
    Parses Usemod index page for topic names.
    
    The parser depends on using this particular auto-generated result page.
    Changes to this will require changes to the parser.
    """
    def __init__(self, name, url, baseUrl, log, updateTimeout):
        self.ina = False
        HTMLParser.HTMLParser.__init__(self)
        BaseParser.__init__(self, name, url, baseUrl, log, updateTimeout)

    def handle_starttag(self, tag, attribs):
        """
        Over-rides HTMLParser method, sets self.ina.
        """
        if tag == 'a':
            for tuple in attribs:
                if tuple[0] == 'class' and tuple[1] == 'wikipagelink':
                    self.ina = True

    def handle_data(self, data):
        """
        Over-rides HTMLParser method
        """
        if self.ina:
            #print data
            self.topics.append(data)
            self.bytes = self.bytes + len(data)

    def handle_endtag(self, tag):
        """
        Over-rides HTMLParser method, clears self.ina.
        """
        if tag == 'a':
            self.ina = False
    
    #BaseParser.updateTopics(self, updateTimeout)

# one instance used per Pmwiki site

class PmwikiSite(BaseSite):
    """
    PmWiki code and site handling.

    @wikisearch add example pmwiki http://www.example.com/wiki http://www.example.com/wiki/Main/SearchWiki?q=%2f
    """
    def __init__ (self, log, db, id):
        BaseSite.__init__(self, log, db, id)
        self._parser = 'pmwikiHTMLParser'
        self._shortName = 'Pmwiki'
        self._urlString = '/'


# one instance used per Pmwiki site

class pmwikiHTMLParser(HTMLParser.HTMLParser, BaseParser):
    """
    Parses PmWiki search result XML for page/topic names.
    
    The parser depends on the formatting of the search result page.
    Changes to this will require changes to the parser.
    """
    def __init__(self, name, url, baseUrl, log, updateTimeout):
        HTMLParser.HTMLParser.__init__(self)
        self.ina = False
        self.inDefList = False
        self.baseUrlLen = len(baseUrl) + 1       # +1 to skip _urlString
        BaseParser.__init__(self, name, url, baseUrl, log, updateTimeout)

    # uses BaseParser.updateTopics()

    def handle_starttag(self, tag, attribs):
        """
        Over-rides HTMLParser method, sets self.ina and self.inDefList.
        """
        if tag == 'dl':
            self.inDefList = True
        elif tag == 'a':
            if self.inDefList:
                for tuple in attribs:
                    if tuple[0] == 'href':
                        self.topics.append(tuple[1][self.baseUrlLen:])
                        self.bytes=self.bytes+len(tuple[1][self.baseUrlLen:])

    def handle_endtag(self, tag):
        """
        Over-rides HTMLParser method, clears self.ina and self.inDefList.
        """
        if tag == 'dl':
            self.inDefList = False
        elif tag == 'a':
            self.ina = False


# one instance used per Trac Wiki site

class TracwikiSite(BaseSite):
    """
    Trac Wiki code and site handling.

    An example Trac Wiki URL to fetch topic names looks like this:
    http://www.example.com/trac/wiki/TitleIndex
    
    @wikisearch add example tracwiki http://www.example.com/t/wiki http://www.example.com/t/wiki/TitleIndex
    """
    def __init__ (self, log, db, id):
        BaseSite.__init__(self, log, db, id)
        self._parser = 'tracwikiHTMLParser'
        self._shortName = 'Tracwiki'
        self._urlString = '/'


# one instance used per Trac Wiki site

class tracwikiHTMLParser(HTMLParser.HTMLParser, BaseParser):
    """
    Parses Trac Wiki TitleIndex for page/topic names.
    
    The parser depends on using this particular auto-generated result page.
    Changes to this will require changes to the parser.
    """
    def __init__(self, name, url, baseUrl, log, updateTimeout):
        HTMLParser.HTMLParser.__init__(self)
        self.ina = False
        self.inUl = False
        self.inHone = False
        self.flagHone = False
        BaseParser.__init__(self, name, url, baseUrl, log, updateTimeout)

    # uses BaseParser.updateTopics()

    def handle_starttag(self, tag, attribs):
        """
        Over-rides HTMLParser method, sets flags for use in handle_data.
        """
        if tag == 'h1':
            self.inHone = True
        elif tag == 'ul':
            self.inUl = True
        elif tag == 'a':
            self.ina = True

    def handle_data(self, data):
        """
        Over-rides HTMLParser method
        """
        if self.inHone:
            if data == 'Title Index': # always true?
                self.flagHone = True
        elif self.flagHone and self.inUl and self.ina:
            self.topics.append(data)
            self.bytes = self.bytes + len(data)

    def handle_endtag(self, tag):
        """
        Over-rides HTMLParser method, clears flags used by handle_data.
        """
        if tag == 'h1':
            self.inHone = False
        elif tag == 'ul':
            self.inUl = False
            self.inHone = False
        elif tag == 'a':
            self.ina = False


# one instance used per Php Wiki site

class PhpwikiSite(BaseSite):
    """
    Php Wiki code and site handling.

    An example Php Wiki URL to fetch topic names looks like this:
    http://www.example.com/AllPages
    
    @wikisearch add example phpwiki http://www.example.com http://www.example.com/AllPages
    """
    def __init__ (self, log, db, id):
        BaseSite.__init__(self, log, db, id)
        self._parser = 'phpwikiHTMLParser'
        self._shortName = 'Phpwiki'
        self._urlString = '/'


# one instance used per Php Wiki site

class phpwikiHTMLParser(HTMLParser.HTMLParser, BaseParser):
    """
    Parses Php Wiki AllPages for page/topic names.
    
    The parser depends on using this particular auto-generated result page.
    Changes to this will require changes to the parser.
    """
    def __init__(self, name, url, baseUrl, log, updateTimeout):
        HTMLParser.HTMLParser.__init__(self)
        self.ina = False
        self.inUl = False
        BaseParser.__init__(self, name, url, baseUrl, log, updateTimeout)

    # uses BaseParser.updateTopics()

    def handle_starttag(self, tag, attribs):
        """
        Over-rides HTMLParser method, sets flags for use in handle_data.
        """
        if tag == 'ul':
            for tuple in attribs:
                if tuple[0] == 'class' and tuple[1] == 'pagelist':
                    self.inUl = True
        elif tag == 'a':
            self.ina = True

    def handle_data(self, data):
        """
        Over-rides HTMLParser method
        """
        if self.inUl and self.ina:
            self.topics.append(data)
            self.bytes = self.bytes + len(data)

    def handle_endtag(self, tag):
        """
        Over-rides HTMLParser method, clears flags used by handle_data.
        """
        if tag == 'ul':
            self.inUl = False
        elif tag == 'a':
            self.ina = False


# one instance used per ZWiki site

class ZwikiSite(BaseSite):
    """
    ZWiki code and site handling.

    An example ZWiki URL to fetch topic names depends on the searchlooks like this:
    http://www.example.com/FrontPage/searchwiki?expr=
    
    @wikisearch add example zwiki http://www.example.com http://www.example.com/FrontPage/searchwiki?expr=
    """
    def __init__ (self, log, db, id):
        BaseSite.__init__(self, log, db, id)
        self._parser = 'zwikiHTMLParser'
        self._shortName = 'ZWiki'
        self._urlString = '/'


# one instance used per ZWiki site

class zwikiHTMLParser(HTMLParser.HTMLParser, BaseParser):
    """
    Parses ZWiki blank search string result HTML page for page/topic names.
    
    The parser depends on using this particular auto-generated result page.
    Changes to this will require changes to the parser.
    """
    def __init__(self, name, url, baseUrl, log, updateTimeout):
        HTMLParser.HTMLParser.__init__(self)
        self.ina = False
        self.inUl = False
        self.baseUrlLen = len(baseUrl) + 1       # +1 to skip _urlString
        BaseParser.__init__(self, name, url, baseUrl, log, updateTimeout)

    # uses BaseParser.updateTopics()

    def handle_starttag(self, tag, attribs):
        """
        Over-rides HTMLParser method, sets flags for use in handle_data.
        """
        if self.inUl:
            if tag == 'a':
                for tuple in attribs:
                    if tuple[0] == 'href':
                        self.topics.append(tuple[1][self.baseUrlLen:])
                        self.bytes=self.bytes+len(tuple[1][self.baseUrlLen:])

    def handle_data(self, data):
        """
        Over-rides HTMLParser method
        """
        if not self.inUl:
            xSearch = re.compile("Page.names.matching")
            if xSearch.search(data):
                self.inUl = True

    def handle_endtag(self, tag):
        """
        Over-rides HTMLParser method, clears flags used by handle_data.
        """
        if tag == 'p':
            self.inUl = False

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:

