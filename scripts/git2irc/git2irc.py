#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# git2irc.py - Notify the Geany IRC channel of Git commits
#
# Copyright 2012 Enrico Tröger <enrico(dot)troeger(at)uvena(dot)de>
# Copyright 2012 Matthew Brush <matt(at)geany(dot)org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301, USA.
#

'''
Sends Git commit notifications to IRC via SweetGeany bot.

Requires a file ``git2irc.conf`` which contains something like this::

  [git]
  repositories=one;or;more;repos

  [irc]
  channel=#thechannel
  host=hostname
  port=portnum

  [shortener]
  url=http://tiny.cc/
  login=apiuser
  key=apikey

Not having any of the sections, options or values will result in a run-time
error. No smart checking is performed.
'''

from cgi import FieldStorage
from json import loads
from urllib2 import urlopen
from urllib import urlencode
import logging
import logging.handlers
import socket
try:
    from configparser import SafeConfigParser  # py3
except ImportError:
    from ConfigParser import SafeConfigParser  # py2


# hard-coded constants, adjust for environment
LOG_FILENAME = '/var/log/git2irc.log'
CONFIG_FILENAME = '/home/geany/git2irc.conf'

# global and cuts across concerns, assumed to be properly initialized later
logger = None  # see init_logging()
config = {'git': {}, 'irc': {}, 'shortener': {}}   # see init_config()


#----------------------------------------------------------------------
def init_config(conf_filename):
    """
    Reads the configuration file into a global dictionary.
    """
    try:
        conf = SafeConfigParser({
                'git': {'repositories': ''},
                'irc': {'channel': '', 'host': '', 'port': 0},
                'shortener': {'url': '', 'login': '', 'key': ''}})
        conf.read(conf_filename)
        config['git']['repositories'] = [itm.strip()
            for itm in conf.get('git', 'repositories').split(';') if itm.strip()]
        config['irc']['channel'] = conf.get('irc', 'channel')
        config['irc']['host'] = conf.get('irc', 'host')
        config['irc']['port'] = int(conf.get('irc', 'port'))
        config['shortener']['url'] = conf.get('shortener', 'url')
        config['shortener']['login'] = conf.get('shortener', 'login')
        config['shortener']['key'] = conf.get('shortener', 'key')
        logger.debug('Read configuration dict: %s' % config)
    # catch-all: will be for invalid config file/section/option, unknown
    # filename, etc
    except Exception as e:
        logger.warn(u"Exception reading config file '%s': %e", conf_filename,
            e, exc_info=True)


#----------------------------------------------------------------------
def init_logging():
    """"
    Initializes the logging file for all to use.
    """
    global logger  # used everywhere
    logger = logging.getLogger('git2irc')
    logger.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler(LOG_FILENAME)
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(name)s: %(levelname)s: %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    # mail
    mail_handler = logging.handlers.SMTPHandler(
        u'localhost',
        u'git-noreply@geany.org',
        [u'enrico.troeger@uvena.de'],
        u'Error on git_post_commit')
    mail_handler.setLevel(logging.WARNING)
    logger.addHandler(mail_handler)
    logger.debug('Logging initialized')


#----------------------------------------------------------------------
def shorten_url(long_url):
    """
    Uses the tiny.cc API to shorten URL's for nice IRC messages.
    """
    req = {'c': 'rest_api',
           'm': 'shorten',
           'version': '2.0.3',
           'format': 'json',
           'shortUrl': '',
           'longUrl': long_url,
           'login': config['shortener']['login'],
           'apiKey': config['shortener']['key']}
    req_enc = urlencode(req)
    req_url = '%s?%s' % (config['shortener']['url'], req_enc)
    short_url = long_url  # default is to return same URL (ie. in case of error)
    try:
        resp_file = urlopen(req_url)
        resp_dict = loads(resp_file.read())
        if int(resp_dict['errorCode']) == 0:
            short_url = resp_dict['results']['short_url']
            logger.debug('Shortened URL: %s' % short_url)
        else:
            logger.warn(u'Error shortening URL: %s: %s' % (
                resp_dict['errorCode'], resp_dict['errorMessage']))
    except Exception as e:  # generally, urllib2.URLError
        logger.warn(u'Exception shortening URL: %e', e, exc_info=True)
    return short_url


#----------------------------------------------------------------------
def send_commit(message):
    """
    Dumps the message to IRC via SweetGeany.
    """
    irc_message = u'Freenode %s %s' % (config['irc']['channel'], message)
    irc_bot_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    irc_bot_socket.connect((config['irc']['host'], config['irc']['port']))
    irc_bot_socket.send(irc_message.encode('utf-8'))
    irc_bot_socket.close()
    logger.debug('Message sent to IRC: %s' % message)


#----------------------------------------------------------------------
def handle_irc_message(repository, content):
    """
    Processes the post-commit-hook from Github.com web hooks.
    """
    try:
        branch = content['ref']
        branch = branch.rsplit('/', 1)[1]
    except (KeyError, IndexError), rev_parse_e:
        logger.warn(u'An error occurred at ref parsing: %s' % rev_parse_e, exc_info=True)
        branch = 'unknown'

    for commit in content['commits']:
        author = commit['author'].get('username', 'Unknown User')
        commit_id = commit['id']
        message = commit['message'].splitlines()[0]
        url = shorten_url(commit['url'])
        irc_line = u'[%s/%s] %s - %s (%s)' % (repository, branch, author, message, url)
        send_commit(irc_line)
        logger.info(u"Sent message to channel '%s' for '%s' (%s)" % (
            config['irc']['channel'], author, commit_id))


#----------------------------------------------------------------------
def main():
    """
    Script entry-point, reads from github.com request and processes the
    event.
    """
    # parse query string
    arguments = FieldStorage(keep_blank_values=True)

    json = arguments.getvalue('payload')
    content = loads(json)
    if 'commits' in content:
        repo = content['repository']['name']
        if repo in config['git']['repositories']:
            handle_irc_message(repo, content)


#----------------------------------------------------------------------
if __name__ == '__main__':

    init_logging()

    logger.debug('Script started')

    init_config(CONFIG_FILENAME)

    try:
        main()
    except Exception, e:
        logger.warn(u'An error occurred: %s' % e, exc_info=True)

    print 'Content-type: text/html'
    print

    logger.debug('Script complete')

    logging.shutdown()
