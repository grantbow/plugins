###
# Copyright (c) 2008, Grant Bowman
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

import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
#import supybot.conf as conf
#import supybot.registry as registry

debianSwirl = """  .''`.
 : :'  :
 `. `'`
   `-
"""

theLc0w = """ (__)
 oo\\~
 !!!!
"""

duck = """ -o /
   \_/"""

emad = """ \||/
 (..)
 -||-
  /\ """

drop = """   .
  .``.
 .    .
 : oo :
 ` -- '
  `''` """

pylogo = """    ...
   :o  :
  .... :..
 '   ..'  `
 :  '     :
 `'': ....'
    :  o:
    `...' """

ubuntutext = """      | |               | |
 _   _| |__  _   _ _ __ | |_ _   _
| | | | '_ \| | | | '_ \| __| | | |
| |_| | |_) | |_| | | | | |_| |_| |
 \__,_|_.__/ \__,_|_| |_|\__|\__,_|"""

dfish = """                  aa##WWg,
                JJ00' 44LL.
               J0000wwjj##00
               ##0000000000@@
              40000000Y'^^
             J00000000Yaaaap
           .00000000000000ll
    __     jj000000000000##'
  j###LL  .000000000000@@((
  j###00..j0000000000000''
  -0000000000000000##''
   40000000000000@@''
   jj0000000000!!
   jj00000099'
   jj!!!! """
fedoralogo= """     .MMMMMMMMM.
   .MMMMMM\"    oo.
 .MMMMMMM\"  \"\"\"MooM
 MMMMMMMM  MMMMMooM.
MMMMoo\"\"\"  \"\"\"oooMMM
MMMooo\"      \"ooMMMM
MMooMMMMM  MMMMMMMM.
MMooM\"\"\"  \"MMMMMMM\"
MMMo     \"MMMMMMM\"
 \"MMMM MMMMMMM\" """

class AsciiArt(callbacks.Plugin):
    """Commands will display ascii artwork.  Use with caution."""
    threaded = True

# Todo - add rate limiter per user or something.

    def _outputArt(self, irc, scriptText):
        """
        performs a time-paced announcement.
        """
        for line in scriptText.splitlines():
            irc.reply(line)
            time.sleep(1)

    def swirl(self, irc, msg, args):
        """takes no arguments

        Display of crafted art.  http://www.debian.org
        """
        self._outputArt(irc, debianSwirl)

    def lc0w(self, irc, msg, args):
        """takes no arguments

        Display of crafted art.  http://www.quakenet.org
        """
        self._outputArt(irc, theLc0w)

    def duck(self, irc, msg, args):
        """takes no arguments

        Display of crafted art.
        """
        self._outputArt(irc, duck)

    def emad(self, irc, msg, args):
        """takes no arguments

        Display of crafted art.  http://zork.net/pipermail/mindjail/2003-July/000049.html
        """
        self._outputArt(irc, emad)

    def drop(self, irc, msg, args):
        """takes no arguments

        Display of crafted art.  http://www.drupal.org
        """
        self._outputArt(irc, drop)

    def pylogo(self, irc, msg, args):
        """takes no arguments

        Display of crafted art.  http://www.python.org
        """
        self._outputArt(irc, pylogo)

    def ubuntutext(self, irc, msg, args):
        """takes no arguments

        Display of crafted art.  http://www.ubuntu.com
        """
        self._outputArt(irc, ubuntutext)

    def dfish(self, irc, msg, args):
        """takes no arguments

        Display of crafted art.  http://www.dreamfish.com
        """
        self._outputArt(irc, dfish)

    def fedoralogo(self, irc, msg, args):
        """takes no arguments

        Display of crafted art.  http://fedoraproject.org
        """
        self._outputArt(irc, fedoralogo)



Class = AsciiArt

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:

