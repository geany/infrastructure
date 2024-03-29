#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author:  Enrico Tröger
# License: GPLv2
#
'''
Github Post-Receive commit hook
'''

import logging
import sys
import urllib.request
from email import charset
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate
from json import loads
from smtplib import SMTP
from time import mktime

from dateutil import parser as dateutil_parser

# Python likes to encode MIME messages with base64, I prefer plain text (#issue12552)
charset.add_charset('utf-8', charset.SHORTEST)

HTTP_REQUEST_TIMEOUT = 30
LOG_LEVEL = logging.DEBUG

EMAIL_SENDER = 'git-noreply@geany.org'
EMAIL_HOST = 'localhost'
EMAIL_SUBJECT_TEMPLATE = '[%(user)s/%(repository)s] %(short_hash)s: %(short_commit_message)s'
EMAIL_BODY_TEMPLATE = '''Branch:      %(branch)s
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
This E-Mail was brought to you by github_commit_mail.py (Source: https://github.com/geany/infrastructure).
'''
EMAIL_DIFF_TEMPLATE = '''Modified: %(filename)s
%(changes)s lines changed, %(additions)s insertions(+), %(deletions)s deletions(-)
===================================================================
%(patch)s


'''

EMAIL_RECIPIENT_MAP = {
    # repository: email address
    # geany
    'geany/geany': 'commits@lists.geany.org',
    'geany/talks': 'commits@lists.geany.org',
    'geany/infrastructure': 'commits@lists.geany.org',
    'geany/www.geany.org': 'commits@lists.geany.org',
    'geany/geany-themes': 'commits@lists.geany.org',
    'geany/geany-osx': 'commits@lists.geany.org',
    # plugins
    'geany/geany-plugins': 'plugins-commits@lists.geany.org',
    'geany/plugins.geany.org': 'plugins-commits@lists.geany.org',
    # newsletter
    'geany/newsletter': 'newsletter-commits@lists.geany.org',
}


class CommitMailGenerator:

    def __init__(self, user, repository, branch, commits, logger):
        self._user = user
        self._repository = repository
        self._branch = branch
        self._commits = commits
        self._logger = logger

    def generate_commit_mails(self):
        for commit in self._commits:
            self._try_to_generate_commit_mail(commit)

    def _try_to_generate_commit_mail(self, commit):
        try:
            self._generate_commit_mail(commit)
        except Exception as exc:
            self._logger.error('An error occurred while processing commit %s: %s',
                               commit, exc, exc_info=True)

    def _generate_commit_mail(self, commit):
        full_commit_info = self._query_commit_info(commit)
        commit_info = self._adapt_commit_info(full_commit_info)
        self._send_mail(commit_info)

    def _query_commit_info(self, commit):
        url = f'https://api.github.com/repos/{self._user}/{self._repository}/commits/{commit}'

        with urllib.request.urlopen(url, timeout=HTTP_REQUEST_TIMEOUT) as handle:
            self._log_rate_limit(handle)
            # parse response
            response_json = handle.read()
            response = loads(response_json)
        return response

    def _log_rate_limit(self, urllib_handle):
        headers = urllib_handle.info()
        rate_limit_remaining = headers.get('X-RateLimit-Remaining', '<unknown>')
        rate_limit = headers.get('X-RateLimit-Limit', '<unknown>')
        length = headers.get('Content-Length', '<unknown>')
        self._logger.debug('Github rate limits: %s/%s (%s bytes received)',
                           rate_limit_remaining, rate_limit, length)

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
        commit_date_formatted = commit_datetime.strftime('%a, %d %b %Y %H:%M:%S %Z')
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

    def _generate_commit_url(self, commit):
        return f'https://github.com/{self._user}/{self._repository}/commit/{commit}'

    def _get_name(self, full_commit_info, name):
        commit_name = full_commit_info['commit'][name]['name']
        commit_email = full_commit_info['commit'][name]['email']
        return f'{commit_name} <{commit_email}>'

    def _parse_commit_date(self, date_raw):
        return dateutil_parser.parse(date_raw)

    def _get_short_commit_message(self, short_commit_message):
        return short_commit_message.splitlines()[0]

    def _generate_modified_files_list(self, full_commit_info):
        modified_files = map(lambda x: x['filename'], full_commit_info['files'])
        files_list = '\n    '.join(modified_files)
        return f'    {files_list}'

    def _generate_modified_files_diffs(self, full_commit_info):
        diffs = ''
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
            diffs += '@@ Diff output truncated at 100000 characters. @@\n'
        return diffs

    def _get_diff_if_available(self, modified_file):
        try:
            return modified_file['patch']
        except KeyError:
            return 'No diff available, check online'

    def _send_mail(self, commit_info):
        author_name = commit_info['author_name'].encode('utf-8')
        author_name = str(Header(author_name, 'UTF-8'))
        content = EMAIL_BODY_TEMPLATE % commit_info
        msg = MIMEText(content.encode('utf-8'), 'plain', 'utf-8')

        msg['Subject'] = EMAIL_SUBJECT_TEMPLATE % commit_info
        msg['From'] = formataddr((author_name, EMAIL_SENDER))
        msg['To'] = self._get_email_recipient()
        msg['Date'] = formatdate(commit_info['commit_date'])

        smtp_conn = SMTP(EMAIL_HOST)
        message = msg.as_string()
        smtp_conn.sendmail(EMAIL_SENDER, msg['To'].split(','), message.encode('utf-8'))
        smtp_conn.quit()

    def _get_email_recipient(self):
        repository = f'{self._user}/{self._repository}'
        # no error handling on purpose, this should bail out if repository is not in the map
        return EMAIL_RECIPIENT_MAP[repository]


class CommandLineArgumentError(Exception):

    def __str__(self):
        return f'Usage: {sys.argv[0]} <user> <repository> <branch> <commit> ...'


def setup_logging():
    logging.basicConfig()
    logger = logging.getLogger('github_commit_mail_hook')
    logger.setLevel(LOG_LEVEL)

    return logger


def parse_command_line_arguments():
    if len(sys.argv) < 5:
        raise CommandLineArgumentError()

    user = sys.argv[1]
    repository = sys.argv[2]
    branch = sys.argv[3]
    commits = sys.argv[4:]

    return user, repository, branch, commits


def main():
    logger = setup_logging()
    try:
        user, repository, branch, commits = parse_command_line_arguments()
        gen = CommitMailGenerator(user, repository, branch, commits, logger)
        gen.generate_commit_mails()
    except CommandLineArgumentError as exc:
        print(exc, file=sys.stderr)
    except Exception as exc:
        logger.warning('An error occurred: %s', str(exc), exc_info=True)
    logging.shutdown()


if __name__ == '__main__':
    main()


# python /misc/github_commit_mail.py geany geany refs/heads/master 85b5e08c471c505b59218b1a94df9b95a01cca06 eb04c514bab87af60f01ae3c8e9ee1d3fd9bccf8 ca922e0ddc8022283ec3c1f49aaa15ab7c5ba213 aa96bc2cbfab0a8033d0ed600541c2d2e0c767bb
