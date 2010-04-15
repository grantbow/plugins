
###
# Copyright (c) 2004,2005,2008,2010 Grant Bowman
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

import time

#import supybot.conf as conf
import supybot.utils as utils    #import supybot.webutils as webutils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
#import supybot.privmsgs as privmsgs
#import supybot.registry as registry
import supybot.callbacks as callbacks

class Meeting(callbacks.PluginRegexp):
    """ Tools for running an IRC meeting.  Currently supports hand raising and
    scripts for opening and closing meetings.  """
    threaded = True
    regexps = ['meetingHand', 'meetingDone']

    def __init__(self, irc):
        callbacks.PluginRegexp.__init__(self, irc)
        self.raisedHands = {} # key is channel, values are a list of tuples
        # example: {'#channel': [('name1', timeInt1), ('name2', timeInt2),]}
        # purposely not using ChannelUserDB or ChannelUserDictionary since I
        # don't need persistence on disk and the interfaces will change if the
        # comments in plugins.__init__.py are accurate
        self._agendaCursor = {} # key is channel, value is an integer
        self._openScript = ''
        self._closeScript = ''
        self._agendaScript = ''

    def loadscripts(self, irc, msg, args, channel):
        """[<channel>]

        Loads the open, close and agenda scripts from URLs.
        """
        x = self.registryValue('openScriptUrl', channel)
        if x:
            self._openScript = utils.web.getUrl(x)
        x = self.registryValue('closeScriptUrl', channel)
        if x:
            self._closeScript = utils.web.getUrl(x)
        x = self.registryValue('agendaScriptUrl', channel)
        if x:
            self._agendaScript = utils.web.getUrl(x)
        irc.replySuccess()

    def _outputAgenda(self, irc, scriptText):
        """
        performs a time-paced announcement for open and close scripts.
        """
        counter = 0
        for line in scriptText.splitlines():
            if line:
                if counter < 9:
                    irc.reply(" %d: %s" % (counter + 1, line))
                else:
                    irc.reply("%d: %s" % (counter + 1, line))
            counter += 1
            time.sleep(1)

    def agenda(self, irc, msg, args, channel):
        """[<channel>]

        Gives the agenda for the meeting.
        """
        if self.registryValue('allowScripts', channel):
            self._outputAgenda(irc, self._agendaScript)

    def _outputAgendaItem(self, irc, pointer, scriptText):
        """
        Gives the (0 based) line number provided, prepended (1 based) number.
        """
        counter = 0
        for line in scriptText.splitlines():
            if counter == pointer:
                if counter < 9:
                    irc.reply(" %d: %s" % (counter + 1, line))
                else:
                    irc.reply("%d: %s" % (counter + 1, line))
                return
            else:
                counter += 1

    def next(self, irc, msg, args, channel, xJump):
        """[<channel>] [<integer>]

        Next agenda item.  Providing an <integer> allows for
        quicker movement.
        """
        self._agendaCursor.setdefault(channel, 0)
        if not self.registryValue('allowScripts', channel):
            return -1
        if xJump:
            self._agendaCursor[channel] += xJump
        else:
            self._agendaCursor[channel] += 1
        x = len(self._agendaScript.splitlines()) - 1
        if self._agendaCursor[channel] > x:
            self._agendaCursor[channel] = x
            irc.reply('End of agenda.')
            return
        self._outputAgendaItem(irc, self._agendaCursor[channel],
                                self._agendaScript)
    next = wrap(next, [optional('channel'), optional('int')])

    def current(self, irc, msg, args, channel):
        """[<channel>]

        Current agenda item.
        """
        self._agendaCursor.setdefault(channel, 0)
        if not self.registryValue('allowScripts', channel):
            return -1
        self._outputAgendaItem(irc, self._agendaCursor[channel],
                                self._agendaScript)

    def previous(self, irc, msg, args, channel, xJump):
        """[<channel>] [<integer>]

        Previous agenda item.  Providing an <integer> allows for
        quicker movement.
        """
        self._agendaCursor.setdefault(channel, 0)
        if not self.registryValue('allowScripts', channel):
            return -1
        self._agendaCursor[channel] -= 1
        if xJump:
            x = len(self._agendaScript.splitlines()) - xJump
        else:
            x = len(self._agendaScript.splitlines()) - 1
        if self._agendaCursor[channel] < 0:
            self._agendaCursor[channel] = 0
            irc.reply('Beginning of agenda.')
            return
        self._outputAgendaItem(irc, self._agendaCursor[channel],
                                self._agendaScript)
    previous = wrap(previous, [optional('channel'), optional('int')])

    def _outputScript(self, irc, scriptText):
        """
        performs a time-paced announcement for open and close scripts.
        """
        for line in scriptText.splitlines():
            irc.reply(line)
            time.sleep(1)

    def open(self, irc, msg, args, channel):
        """[<channel>]

        Gives the openinging meeting script.
        """
        if self.registryValue('allowScripts', channel):
            self._outputScript(irc, self._openScript)
    open = wrap(open, [('checkChannelCapability', 'op')])

    def close(self, irc, msg, args, channel):
        """[<channel>]

        Gives the closing meeting script.
        """
        if self.registryValue('allowScripts', channel):
            self._outputScript(irc, self._closeScript)
    close = wrap(close, [('checkChannelCapability', 'op')])

    def _waitTime(self, lastTime):
        """
        returns the number of minutes and seconds since lastTime.
        """
        interval = int(time.time()) - lastTime
        m = int(interval/60)
        s = int(interval - m * 60)
        return (m, s)

    def _raisedHandsReply(self, channel, withTime=False):
        """
        Constructs a reply of raised hands with optional queue time.
        """
        x = len(self.raisedHands[channel])
        if x == 0:
            return self.registryValue('noRaised', channel)
        elif x == 1:
            return self.raisedHands[channel][0][0] + \
                   self.registryValue('onlyRaised', channel)
        else: # > 1
            _nameList = []
            doneFirst = False
            for tuple in self.raisedHands[channel]:
                if not doneFirst:
                    firstText = self.raisedHands[channel][0][0] + \
                           self.registryValue('onlyRaised', channel)
                    doneFirst = True
                else:
                    (m, secs) = self._waitTime(tuple[1])
                    # m could be zero or more minutes
                    if withTime:
                        _nameList.append('%s %s:%02d' % (tuple[0],
                                                         str(m), secs))
                    else:
                        _nameList.append('%s' % (tuple[0]))
            return '%s %s %s' % (firstText, self.registryValue('raisedIntro',
                    channel), utils.commaAndify(_nameList))

    def hands(self, irc, msg, args, channel):
        """[<channel>]

        Returns the list of raised hands.
        """
        self.raisedHands.setdefault(channel, [])
        irc.reply(self._raisedHandsReply(channel))
    hands = wrap(hands, [('inchannel')])

    def waittimes(self, irc, msg, args, channel):
        """[<channel>]

        Returns the list of raised hands with wait times shown.
        """
        self.raisedHands.setdefault(channel, [])
        irc.reply(self._raisedHandsReply(channel, withTime=True))
    waittimes = wrap(waittimes , [('inchannel')])

    def clearhands(self, irc, msg, args, channel):
        """[<channel>]

        Returns the list of raised hands and clears the queue.  Should not be
        necessary very often.
        """
        self.raisedHands.setdefault(channel, [])
        _list = []
        for it in self.raisedHands[channel]:
            _list.append(it[0])
        irc.reply('Clearing raised hands - ' + utils.commaAndify(_list))
        self.raisedHands[channel] = []
        # needs security
    clearhands = wrap(clearhands, [('checkChannelCapability', 'op', 'inchannel')])

    def meetingHand(self, irc, msg, match):
        r"^([hH]and).?.?$"
	channel = msg.args[0]
        hit = False
        self.raisedHands.setdefault(channel, [])
        for tuple in self.raisedHands[channel]:
            if msg.nick == tuple[0]:
                # msg.nick in raisedHands somewhere
                hit = True
                (m, s) = self._waitTime(tuple[1])
                if tuple == self.raisedHands[channel][0]:
                    # msg.nick already has the floor.
                    irc.reply(msg.nick + self.registryValue('floorAndRaised',
                                                            channel))
                else:
                    # msg.nick isn't speaking now, must be anxious
                    if self.registryValue('allowVerbose', channel):
                        irc.reply('Your hand has been raised ' +
                            '%s minutes and %s seconds.' % (str(m), str(s)))
                    else:
                        irc.reply(self.registryValue('confirm', channel))
        if not hit:
            # append tuple (msg.nick, int(time.time)) to channel's list
            if len(self.raisedHands[channel]) > 0: # others waiting
                self.raisedHands[channel].append((msg.nick, int(time.time())))
                irc.reply(self.registryValue('confirm', channel))
            else:
                self.raisedHands[channel].append((msg.nick, int(time.time())))
                irc.reply(self.registryValue('noRaisedHand', channel))

    def meetingDone(self, irc, msg, match):
        r"([dD]one|[uU]nhand).?.?$"
	channel = msg.args[0]
        hit = False
        self.raisedHands.setdefault(channel, [])
        for tuple in self.raisedHands[channel]:
            # remove all of nick's entries, though only one should exist
            if msg.nick == tuple[0]:
                hit = True
                self.raisedHands[channel].remove(tuple)
        if hit:
            if self.registryValue('allowVerbose', channel):
                irc.reply('Thank you, %s. ' % (msg.nick))
                irc.reply(self._raisedHandsReply(channel))
            else:
                irc.reply(self._raisedHandsReply(channel))
        #else:
            # done, yet msg.nick not in raisedHands: ignore

Class = Meeting


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:

