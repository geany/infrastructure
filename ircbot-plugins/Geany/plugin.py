###
# -*- coding: utf-8 -*-
# Copyright (c) 2003-2005, Jeremiah Fincher
# Copyright (c)      2010, Enrico Tröger
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

from timer import RepeatTimer

import random
import threading
from ConfigParser import SafeConfigParser

import supybot.utils as utils
from supybot.commands import *
import supybot.ircmsgs as ircmsgs
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks

import supybot.conf as conf


GOODIES = {
    'coffee': 'A nice sexy waitress brings %s a big cup of coffee!',
    'coke': 'A nice sexy waitress brings %s a cool bottle of coke!',
    'pepsi': 'A nice sexy waitress brings %s a cool bottle of Pepsi!',
    'juice': 'A nice sexy waitress brings %s a glass of fresh juice!',
    'vodka': 'A nice sexy waitress brings %s a shot glass of vodka!',
    'beer': 'A nice sexy waitress brings %s a nice bottle of beer!',
    'tea': 'A nice sexy waitress brings %s a cup of hot tea!',
    'milk': 'A nice sexy waitress brings %s a glass of fresh, cold milk',
    'chocolate': 'A nice sexy waitress brings %s a piece of sweet chocolate',
    'pizza': 'Someone calls Mario, and he brings %s a tasty hawaiian pizza!'
};


class Geany(callbacks.Plugin):
    def __init__(self, irc):
        self.__parent = super(Geany, self)
        self.__parent.__init__(irc)
        self.timer = RepeatTimer(180.0, self._write_user_list, self.log, 0, [irc])
        self.timer.start()
        self.help_database = {}
        self._read_help_database()

    def die(self):
        if self.timer:
            threading.Thread(target=self.timer.cancel).start()

    def _read_help_database(self):
        config = SafeConfigParser()
        config.read('help_database.rc')
        for key, value in config.items('general'):
            self.help_database[key] = value

    def _write_help_database(self):
        conv = lambda dic: ['%s: %s' % (k, v) for (k, v) in dic.iteritems()]
        data = conv(self.help_database)
        data.sort()
        f = open('help_database.rc', 'w')
        f.write('[general]\n')
        f.write('\n'.join(data))
        f.close()

    def _write_user_list(self, irc):
        exclude_nicks = [ 'ChanServ', self._get_nick_name() ]
        def filter_services(value):
            return value not in exclude_nicks

        if hasattr(irc, 'getRealIrc'):
            state = irc.getRealIrc().state
        elif hasattr(irc, 'state'):
            state = irc.state
        else:
            state = None

        if state:
            channel_users = state.channels['#geany'].users
            # filter myself and ChanServ
            users = filter(filter_services, channel_users)

            f = open('/srv/www/irc.geany.org/irc_userlist', 'w')
            f.write('\n'.join(users))
            f.close()

    def _get_nick_name(self):
        """
        Return the configured nick name
        """
        return str(conf.supybot.nick)
        #~ return self.registryValue('nick')

    def _get_command_name(self, msg, fallback='help'):
        """
        Parse and return the actual command name
        """
        try:
            cmd = msg.args[1].split()[0]
            if cmd[0] == '!':
                cmd = cmd[1:]
        except:
            cmd = fallback
        return cmd

    def _process_help_request(self, irc, text):
        if text == 'keywords':
            keywords = sorted(self.help_database.keys())
            irc.reply(' '.join(keywords))
            return

        try:
            result = self.help_database[text]
            if result:
                while result[0] == '@':
                    # read alias
                    # (The outer while loop could easily cause endless lookups if there are
                    # circular aliases defined, let's hope users stay nice.)
                    result = self.help_database[result[1:]]
                irc.reply(result)
        except KeyError:
            pass

    def doPrivmsg(self, irc, msg):
        (recipients, text) = msg.args
        if text.startswith('?? '):
            self._process_help_request(irc, text[3:])

    def goodie(self, irc, msg, args, text):
        """takes no arguments

        Request a goodie
        """
        if not text:
            rcpt = msg.nick
        else:
            text = text[0].split()
            if len(text) > 1:
                if text[0] == 'for':
                    if text[1] == 'me':
                        rcpt = msg.nick
                    else:
                        rcpt = text[1]
                else:
                    rcpt = text[0]
            else:
                rcpt = text[0]

        cmd = self._get_command_name(msg, 'tea')
        try:
            irc.reply(GOODIES[cmd] % rcpt)
        except KeyError:
            pass

    def listgoodies(self, irc, msg, args, text):
        """takes no arguments

        Lists available goodies
        """
        available_goodies = sorted(GOODIES.keys())
        available_goodies = ', '.join(available_goodies)
        text = 'A nice sexy waitress offers the following goodies for you: %s' % available_goodies
        irc.reply(text)

    def hello(self, irc, msg, args, text):
        """takes no arguments

        Greetings
        """
        cmd = self._get_command_name(msg, 'hi')
        text = 'Hi %s. My name is %s and I\'m here to offer additional services to you! Try \"?? help\" for general information.' % (msg.nick, self._get_nick_name())
        irc.reply(text)

    def thanks(self, irc, msg, args, text):
        """takes no arguments

        Thanks
        """
        cmd = self._get_command_name(msg, 'thanks')
        text = '%s, no problem. It was a pleasure to serve you.' % (msg.nick)
        irc.reply(text)

    def test(self, irc, msg, args, text):
        """takes no arguments

        Bah, tests
        """
        irc.reply('I don\'t like tests!')

    def _learn(self, key, value):

        update = key in self.help_database

        self.help_database[key] = value

        self._write_help_database()

        return update

    def learn(self, irc, msg, args, key, value):
        """newKeyword Text...

        With the command !learn you can add new keywords to the database.
        Use "!learn newKeyword Text which should be added" to add new keywords.
        Use this with care!
        """
        update = self._learn(key, value)

        if update:
            irc.reply('Existing keyword "%s" was updated' % key)
        else:
            irc.reply('New keyword "%s" was added' % key)

    def alias(self, irc, msg, args, dest, source):
        """newWord existingWord

        Type '!alias newWord existingWord' to create a new alias, e.g. '!alias svn subversion'.
        """
        if not source in self.help_database:
            irc.reply('Alias "%s" could not be created because the target does not exist' % dest)
            return

        update = self._learn(dest, '@%s' % source)

        if update:
            irc.reply('Existing alias "%s" was updated' % dest)
        else:
            irc.reply('New alias "%s" was added' % dest)

    def moo(self, irc, msg, args):
        """takes no arguments

        Have you mooed today?
        """
        if random.randrange(0, 2):
            text = """         ^__^
         (oo)
   /-----(__)
  / |    ||
 *  /\\---/\\
    ~~   ~~
.."Have you mooed today?".."""
            for line in text.split('\n'):
                irc.reply(line)
        else:
            irc.reply('I have Super Cow Powers. Have you mooed today?')

    def commit(self, irc, msg, args, idx):
        """takes one argument, a Git ID SHA

        Type '!commit <SHA-ID-HERE>' to print a URL/link to view the commit
        in Geany's online Git repository browser.
        """
        idx = str(idx).lower().strip()
        if all(ch in 'abcdef0123456789' for ch in idx):
            irc.reply('https://github.com/geany/geany/commit/' + idx)
            # using Github since it allows shortened SHAs also
            #irc.reply('http://git.geany.org/geany/commit/?id=' + idx)
        else:
            irc.reply('Malformed Git SHA')

    # "decorate" our commands (wrap is a decorator replacement for old Python versions)
    tea = wrap(goodie, [ optional(many('text')) ])
    coffee = wrap(goodie, [ optional(many('text')) ])
    coke = wrap(goodie, [ optional(many('text')) ])
    pepsi = wrap(goodie, [ optional(many('text')) ])
    juice = wrap(goodie, [ optional(many('text')) ])
    vodka = wrap(goodie, [ optional(many('text')) ])
    beer = wrap(goodie, [ optional(many('text')) ])
    pizza = wrap(goodie, [ optional(many('text')) ])
    chocolate = wrap(goodie, [ optional(many('text')) ])
    milk = wrap(goodie, [ optional(many('text')) ])
    goodies = wrap(listgoodies, [ optional(many('text')) ])
    goods = wrap(listgoodies, [ optional(many('text')) ])


    hi = wrap(hello, [ optional(many('text')) ])
    hello = wrap(hello, [ optional(many('text')) ])
    hey = wrap(hello, [ optional(many('text')) ])

    thanks = wrap(thanks, [ optional(many('text')) ])
    thankyou = wrap(thanks, [ optional(many('text')) ])
    thx = wrap(thanks, [ optional(many('text')) ])

    learn = wrap(learn, [ 'something', 'text' ])
    alias = wrap(alias, [ 'something', 'something' ])

    test = wrap(test, [ optional(many('text')) ])
    moo = wrap(moo)
    commit = wrap(commit, [ 'text' ])



Class = Geany


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
