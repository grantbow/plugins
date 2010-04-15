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

from supybot.commands import *
import supybot.conf as conf
import supybot.utils as utils
import supybot.ircdb as ircdb
import supybot.plugins as plugins
#import supybot.privmsgs as privmsgs
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks


class Hello(callbacks.Plugin):
    """This plugins provides interactive tutorials in using your Supybot.
    Available commands are: hello, tutorialone, tutorialtwo, tutorialthree
    commandhelp, createuserhelp, newownerhelp and registryhelp."""

    helloMessage = 'Hello, you are talking to a Supybot named \'%s\'.  \
Please use private messages (/msg %s ...) to explore new commands.  %sFor \
online documentation see the http://www.supybot.org website.  To see \
more text just type "more" in this window.  Note that the \
owners have chosen to enable a subset of available Supybot plugins.  Using \
private messages to learn about \'%s\' is encouraged so you can learn at \
your own pace.  Supybot provides information to IRC users by private \
messages or in a channel.  Please take a few \
moments to learn the basic commands in the following three step tutorial. \
You can return here by issuing this "hello" command at any time.  \
Once you are up to speed more advanced features can be discovered at your own \
pace. The most important of the Supybot commands are "list" and "help". \
Advanced users can jump to the "createuserhelp" or "commandhelp" tutorials.  \
Try the "list" command now, then type "tutorialone" to continue.'
    tutorialOneMessage = 'Great.  The list command shows all the plugins \
loaded for %s.  Supybot features are grouped into plugins that each have \
a set of commands.  This fixed, two tier hierarchy will seem more helpful \
once you get used to it.  This structure is needed because Supybot is \
expandable.  It can be set up by itself with just the six required plugins \
or many plugins.  It is not necessary to learn about all the commands \
in all the plugins of %s to use it effectively.  This tutorial is designed \
to get you started quickly with the most important commands for %s or any \
Supybot.  Try the "list Hello" command then "tutorialtwo" to continue.'
    tutorialTwoMessage = 'Great.  All private messages to %s are assumed to \
be commands.  Commands given in a channel are recognized as commands (by \
default) only if they begin with \'%s\' or \'%s\'.  Each plugin distributed \
with Supybot is listed on the http://www.supybot.org website, but interactive \
documentation is readily available using the "help" command followed by the \
command name.  To tell what plugins provide a command you can use the \
"plugin" command.  Try the commands "help hello", "plugin hello" and "plugin \
list" then "tutorialthree" to continue.'
    tutorialThreeMessage = 'The hope is that many Supybot features are self \
documenting.  To search for a command who\'s name you forgot you can use the \
"apropos" command with a substring to search available command names.  You \
can try "apropos default" later to explore some other useful commands. \
Additional documentation is available with the source distribution or using \
four other commands provided by the the Hello plugin.     1. "commandhelp" \
gives more details about the command structure. 2. "createuserhelp" describes \
how to register using the "register" command and identify manually using the \
"identify" command or automatically after using the "hostmask add" command. \
Some plugins and commands require a user to be registered. 3. "newownerhelp" \
gives basic information needed by new owners or power users. 4. \
"registryhelp" dives into the advanced features provided by the Supybot \
registry system and the "config" command used by many plugins in different \
ways.  Have fun exploring!'
    commandsMessage = 'Available commands \
are grouped into plugins.  For a list of the plugins loaded by the \
owner(s) use the "list" command.  Six plugins are always loaded: \
Admin, Channel, Config, Misc, Owner and User.  To see the commands \
grouped in a plugin (such as User) give the command "list User".  For \
help using a particular command use the "help" command.  Some commands \
like "list" are provided by many different plugins.  To see what plugins \
provide a command, use the "plugin" command.  Commands named identically \
provided by different plugins can be called by using the name of \
the plugin before the command.  Defaults can be set using the \
"defaultplugin" command.  If you forget the name of a command the \
"apropos" command can be used to search for commands with a string you \
provide.'
    createUserMessage = 'A User system implemented in the User plugin \
provides an authentication feature based on user names, passwords and \
optionally IRC host IDs.  User permissions can control who can use some \
commands through Supybot \'capabilities\'.  To register as a user of this \
bot, use the "register" command.  You can then use the "identify" command \
to authenticate with your password.  To automatically authenticate on many \
irc servers you can add a hostmask to your user account.  To add your \
current hostmask to your identified username use the command "hostmask add \
[hostmask]".  As you can see, nested commands use square brackets.  Some \
new features can be provided by setting up aliases using the Alias plugin.'
    newOwnerMessage = 'Supybot is highly configurable.  This bot\'s \
owner(s) used the "config", "config list", "config search" and "config \
help" commands to check and change configuration values in the registry.'
    registryMessage = 'The Supybot registry contains many important \
settings.  Like the regular list and help commands, config has sub-commands \
used to list and get help on registry groups.  When listing registry values, \
some values have characters that denote that the registry entrey has \
children (@) below it that can be listed and and channel-specific groups \
(#).  Channel-specific groups are most easily changed by issuing the config \
command from the channel itself.  The behavior of Supybot can be extremely \
customized using the various registry entries.  Viewing and setting a \
registry values is done with the "config" command without a sub-command. \
If only one argument is provided it is assumed to be a registry value name \
and the value is provided.  If two arguments are provided it is set to the \
given value.  The registry can be flushed manually using the "flush" command \
and is automatically flushed every few minutes if the registry value of \
supybot.flush is True.  The hope is that many Supybot features are self \
documenting including the use of the registry values.  Try "config list \
supybot.plugins" now to begin exploring.  Have fun!'

    def hello(self, irc, msg, args):
        """ requires no arguments

        Replies with a greeting.
        """
        x = irc.irc.nick
        xOwners = []
        for u in ircdb.users.itervalues():
            try:
                if u.checkCapability('owner'):
                    xOwners.append(u.name)
            except:
                pass
        if xOwners:
            utils.sortBy(str.lower, xOwners)
            y = 'The registered \'owners\' of this bot are %s. ' \
                'Please report any problems with \'%s\' to them. ' % (
                utils.commaAndify(xOwners), x) 
        else:
            y = ''
        irc.reply(self.helloMessage % (x, x, y, x),
            to=msg.nick, prefixNick=False, private=True)
    hello = wrap(hello)

    # hi is just an alias of the same command.
    hi = hello

    def tutorialone(self, irc, msg, args):
        """ requires no arguments

        Replies with the first part of the tutorial.
        """
        x = irc.irc.nick
        irc.reply(self.tutorialOneMessage % (x, x, x),
            to=msg.nick, prefixNick=False, private=True)
    tutorialone = wrap(tutorialone)

    def tutorialtwo(self, irc, msg, args):
        """ requires no arguments

        Replies with the second part of the tutorial.
        """
        x = irc.irc.nick
        if conf.supybot.reply.whenAddressedBy.chars:
            xChar = conf.supybot.reply.whenAddressedBy.chars
        else:
            xChar = "@"
        irc.reply(self.tutorialTwoMessage % (x, x, xChar),
            to=msg.nick, prefixNick=False, private=True)
    tutorialtwo = wrap(tutorialtwo)

    def tutorialthree(self, irc, msg, args):
        """ requires no arguments

        Replies with the third part of the tutorial.
        """
        irc.reply(self.tutorialThreeMessage,
            to=msg.nick, prefixNick=False, private=True)
    tutorialthree = wrap(tutorialthree)

    def commandhelp(self, irc, msg, args):
        """ requires no arguments

        Replies with a instructions for exploring commands.
        """
        irc.reply(self.commandsMessage,
            to=msg.nick, prefixNick=False, private=True)
    commandhelp = wrap(commandhelp)

    def createuserhelp(self, irc, msg, args):
        """ requires no arguments

        Replies with a instructions for creating a user account.
        """
        irc.reply(self.createUserMessage,
            to=msg.nick, prefixNick=False, private=True)
    createuserhelp = wrap(createuserhelp)

    def newownerhelp(self, irc, msg, args):
        """ requires no arguments

        Replies with a instructions for new admins and power users.
        """
        irc.reply(self.newOwnerMessage,
            to=msg.nick, prefixNick=False, private=True)
    newownerhelp = wrap(newownerhelp)

    def registryhelp(self, irc, msg, args):
        """ requires no arguments

        Replies with a instructions for exploring the registry.
        """
        irc.reply(self.registryMessage,
            to=msg.nick, prefixNick=False, private=True)
    registryhelp = wrap(registryhelp)


Class = Hello


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
