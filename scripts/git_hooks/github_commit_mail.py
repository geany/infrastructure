#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author:  Enrico Tröger
# License: GPLv2
#
'''
Github Post-Receive commit hook
'''


from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.Header import Header
from email.utils import formatdate, formataddr
from json import loads
from smtplib import SMTP
from time import mktime
import logging
import sys
import urllib2
# Python likes to encode MIME messages with base64, I prefer plain text (#issue12552)
from email import charset
charset.add_charset('utf-8', charset.SHORTEST)


HTTP_REQUEST_TIMEOUT = 30
LOG_LEVEL = logging.DEBUG

EMAIL_SENDER = u'git-noreply@geany.org'
EMAIL_HOST = u'localhost'
EMAIL_SUBJECT_TEMPLATE = u'[%(user)s/%(repository)s] %(short_hash)s: %(short_commit_message)s'
EMAIL_BODY_TEMPLATE = u'''Branch:      %(branch)s
Author:      %(author)s
Committer:   %(committer)s
Date:        %(commit_date_formatted)s
Commit:      %(commit)s
             %(commit_url)s

Log Message:
-----------
%(commit_message)s


Modified Paths:
--------------
%(modified_files_list)s

%(modified_files_diffs)s
--------------
This E-Mail was brought to you by github_commit_mail.py (Source: TBD).
'''
EMAIL_DIFF_TEMPLATE = u'''Modified: %(filename)s
%(changes)s files changed, %(additions)s insertions(+), %(deletions)s deletions(-)
===================================================================
%(patch)s


'''

EMAIL_RECIPIENT_MAP = {
    # repository: email address
    # geany
    'geany/geany': 'geany-commits@uvena.de',
    'geany/talks': 'geany-commits@uvena.de',
    'geany/infrastructure': 'geany-commits@uvena.de',
    # plugins
    'geany/geany-plugins': 'geany-plugins-commits@uvena.de',
    'geany/plugins.geany.org': 'geany-plugins-commits@uvena.de',
    # newsletter
    'geany/newsletter': 'geany-newsletter-commits@uvena.de',
}


########################################################################
class CommitMailGenerator(object):
    """"""

    #----------------------------------------------------------------------
    def __init__(self, user, repository, branch, commits, logger):
        self._user = user
        self._repository = repository
        self._branch = branch
        self._commits = commits
        self._logger = logger

    #----------------------------------------------------------------------
    def generate_commit_mails(self):
        for commit in self._commits:
            self._try_to_generate_commit_mail(commit)

    #----------------------------------------------------------------------
    def _try_to_generate_commit_mail(self, commit):
        try:
            self._generate_commit_mail(commit)
        except Exception, e:
            self._logger.error('An error occurred while processing commit %s: %s' %
                (commit, e), exc_info=True)

    #----------------------------------------------------------------------
    def _generate_commit_mail(self, commit):
        full_commit_info = self._query_commit_info(commit)
        commit_info = self._adapt_commit_info(full_commit_info)
        self._send_mail(commit_info)

    #----------------------------------------------------------------------
    def _query_commit_info(self, commit):
        url_parameters = dict(user=self._user,
                              repository=self._repository,
                              commit=commit)
        url = u'https://api.github.com/repos/%(user)s/%(repository)s/commits/%(commit)s' % \
            url_parameters
        handle = urllib2.urlopen(url, timeout=HTTP_REQUEST_TIMEOUT)
        self._log_rate_limit(handle)
        # parse response
        response_json = handle.read()
        response = loads(response_json)
        return response

    #----------------------------------------------------------------------
    def _log_rate_limit(self, urllib_handle):
        headers = urllib_handle.info()
        rate_limit_remaining = headers['X-RateLimit-Remaining']
        rate_limit = headers['X-RateLimit-Limit']
        length = headers['Content-Length']
        self._logger.debug(u'Github rate limits: %s/%s (%s bytes received)' %
            (rate_limit_remaining, rate_limit, length))

    #----------------------------------------------------------------------
    def _adapt_commit_info(self, full_commit_info):
        branch = self._branch
        commit = full_commit_info['sha']
        commit_url = self._generate_commit_url(commit)
        author = self._get_name(full_commit_info, 'author')
        author_name = full_commit_info['commit']['author']['name']
        committer = self._get_name(full_commit_info, 'committer')
        committer_name = full_commit_info['commit']['committer']['name']
        commit_datetime = self._parse_commit_date(full_commit_info['commit']['committer']['date'])
        commit_date = mktime(commit_datetime.timetuple())
        commit_date_formatted = commit_datetime.strftime('%a, %d %b %Y %H:%M:%S')
        commit_message = full_commit_info['commit']['message']
        short_commit_message = self._get_short_commit_message(commit_message)
        short_hash = commit[:6]
        modified_files_list = self._generate_modified_files_list(full_commit_info)
        modified_files_diffs = self._generate_modified_files_diffs(full_commit_info)

        return dict(user=self._user,
                    repository=self._repository,
                    commit=commit,
                    commit_url=commit_url,
                    branch=branch,
                    author=author,
                    author_name=author_name,
                    committer=committer,
                    committer_name=committer_name,
                    commit_date=commit_date,
                    commit_date_formatted=commit_date_formatted,
                    commit_message=commit_message,
                    short_commit_message=short_commit_message,
                    short_hash=short_hash,
                    modified_files_list=modified_files_list,
                    modified_files_diffs=modified_files_diffs)

    #----------------------------------------------------------------------
    def _generate_commit_url(self, commit):
        url_parameters = dict(user=self._user,
                              repository=self._repository,
                              commit=commit)
        return u'https://github.com/%(user)s/%(repository)s/commit/%(commit)s' % url_parameters

    #----------------------------------------------------------------------
    def _get_name(self, full_commit_info, name):
        return u'%s <%s>' % (full_commit_info['commit'][name]['name'],
                             full_commit_info['commit'][name]['email'])

    #----------------------------------------------------------------------
    def _parse_commit_date(self, date_raw):
        # unfortunately, Python's strptime cannot parse numeric timezone offsets (anymore since 2.6)
        # so we need to do it on our own, example date: 2012-01-08T04:44:21-08:00
        date_to_parse = date_raw[:-6]
        timezone_offset = date_raw[-6:]
        # parse date
        date = datetime.strptime(date_to_parse, '%Y-%m-%dT%H:%M:%S')
        # handle timezone information
        timezone_offset = timezone_offset.replace(':', '')
        try:
            offset = int(timezone_offset)
        except ValueError:
            self._logger.warn(
                u'Error on parsing timezone information "%s" (%s)' % (timezone_offset, date_raw))
            offset = 0

        delta = timedelta(hours=offset / 100.0)
        date -= delta
        return date

    #----------------------------------------------------------------------
    def _get_short_commit_message(self, short_commit_message):
        return short_commit_message.splitlines()[0]

    #----------------------------------------------------------------------
    def _generate_modified_files_list(self, full_commit_info):
        modified_files = map(lambda x: x['filename'], full_commit_info['files'])
        return u'    %s' % u'\n    '.join(modified_files)

    #----------------------------------------------------------------------
    def _generate_modified_files_diffs(self, full_commit_info):
        diffs = u''
        for modified_file in full_commit_info['files']:
            parameters = dict(filename=modified_file['filename'],
                              changes=modified_file['changes'],
                              additions=modified_file['additions'],
                              deletions=modified_file['deletions'],
                              patch=self._get_diff_if_available(modified_file))
            diffs += EMAIL_DIFF_TEMPLATE % parameters
        # shrink diffs to at most ~ 100KB
        if len(diffs) > 100000:
            diffs = diffs[:100000]
            diffs += u'@@ Diff output truncated at 100000 characters. @@\n'
        return diffs

    #----------------------------------------------------------------------
    def _get_diff_if_available(self, modified_file):
        try:
            return modified_file['patch']
        except KeyError:
            return u'No diff available, check online'

    #----------------------------------------------------------------------
    def _send_mail(self, commit_info):
        author_name = commit_info['author_name'].encode('utf-8')
        author_name = str(Header(author_name, 'UTF-8'))
        content = EMAIL_BODY_TEMPLATE % commit_info
        msg = MIMEText(content, 'plain', 'utf-8')

        msg['Subject'] = EMAIL_SUBJECT_TEMPLATE % commit_info
        msg['From'] = formataddr((author_name, EMAIL_SENDER))
        msg['To'] = self._get_email_recipient()
        msg['Date'] = formatdate(commit_info['commit_date'])

        smtp_conn = SMTP(EMAIL_HOST)
        smtp_conn.sendmail(EMAIL_SENDER, msg['To'].split(','), msg.as_string())
        smtp_conn.quit()

    #----------------------------------------------------------------------
    def _get_email_recipient(self):
        repository = u'%s/%s' % (self._user, self._repository)
        # no error handling on purpose, this should bail out if repository is not in the map
        return EMAIL_RECIPIENT_MAP[repository]


########################################################################
class CommandLineArgumentError(Exception):

    #----------------------------------------------------------------------
    def __str__(self):
        return 'Usage: %s <user> <repository> <branch> <commit> ...' % sys.argv[0]


#----------------------------------------------------------------------
def setup_logging():
    logging.basicConfig()
    logger = logging.getLogger('github_commit_mail_hook')
    logger.setLevel(LOG_LEVEL)

    return logger


#----------------------------------------------------------------------
def parse_command_line_arguments():
    if len(sys.argv) < 5:
        raise CommandLineArgumentError()

    user = sys.argv[1]
    repository = sys.argv[2]
    branch = sys.argv[3]
    commits = sys.argv[4:]

    return user, repository, branch, commits


#----------------------------------------------------------------------
def main():
    logger = setup_logging()
    try:
        user, repository, branch, commits = parse_command_line_arguments()
        gen = CommitMailGenerator(user, repository, branch, commits, logger)
        gen.generate_commit_mails()
    except CommandLineArgumentError, e:
        print >> sys.stderr, e
    except Exception, e:
        logger.warn(u'An error occurred: %s' % e, exc_info=True)
    logging.shutdown()


if __name__ == '__main__':
    main()


# python /misc/github_commit_mail.py geany geany refs/heads/master 85b5e08c471c505b59218b1a94df9b95a01cca06 eb04c514bab87af60f01ae3c8e9ee1d3fd9bccf8 ca922e0ddc8022283ec3c1f49aaa15ab7c5ba213 aa96bc2cbfab0a8033d0ed600541c2d2e0c767bb
