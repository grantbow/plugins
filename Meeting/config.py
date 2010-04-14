###
# Copyright (c) 2004,2005,2008, Grant Bowman
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

import supybot.conf as conf
import supybot.registry as registry

def configure(advanced):
    # This will be called by supybot to configure this module.  advanced is
    # a bool that specifies whether the user identified himself as an advanced
    # user or not.  You should effect your configuration by manipulating the
    # registry as appropriate.
    from supybot.questions import expect, anything, something, yn
    conf.registerPlugin('Meeting', True)


Meeting = conf.registerPlugin('Meeting')

conf.registerChannelValue(conf.supybot.plugins.Meeting, 'allowScripts',
    registry.Boolean(True, """Determines whether the open, close and
    agenda related commands are allowed."""))
conf.registerChannelValue(conf.supybot.plugins.Meeting, 'raisedIntro',
    registry.String('Other raised hands (in order):', """Determines the
    text used for listing raised hands."""))
conf.registerChannelValue(conf.supybot.plugins.Meeting, 'noRaised',
    registry.String('No more raised hands.', """Determines the text used
    when no hands are raised."""))
conf.registerChannelValue(conf.supybot.plugins.Meeting, 'onlyRaised',
    registry.String(', go ahead.', """Determines the text used
    when only one hand is raised."""))
conf.registerChannelValue(conf.supybot.plugins.Meeting, 'noRaisedHand',
    registry.String('You are next. If you aren\'t interrupting, ' \
    'go ahead now.', """Determines the text used when
    no other hands are raised."""))
conf.registerChannelValue(conf.supybot.plugins.Meeting, 'floorAndRaised',
    registry.String(', go ahead. Others now speaking should ' \
    'wait their turn.', """Determines the text used when the current
    speaker's hand is raised again."""))
conf.registerChannelValue(conf.supybot.plugins.Meeting, 'allowVerbose',
    registry.Boolean(False, """Determines whether the text replies are
    verbose.  Effects hand and done."""))
conf.registerChannelValue(conf.supybot.plugins.Meeting, 'confirm',
    registry.String('Ok', """Determines the text reply when confirming a
    raised hand and someone else has the floor."""))
conf.registerChannelValue(conf.supybot.plugins.Meeting, 'openScriptUrl',
    registry.String('', """Determines the URL for a text file.  """))
conf.registerChannelValue(conf.supybot.plugins.Meeting, 'closeScriptUrl',
    registry.String('', """Determines the URL for a text file.  """))
conf.registerChannelValue(conf.supybot.plugins.Meeting, 'agendaScriptUrl',
    registry.String('', """Determines the URL for a text file.  """))


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
