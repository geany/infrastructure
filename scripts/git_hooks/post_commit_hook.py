#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author:  Enrico Tröger
# License: GPLv2
#
'''
Geany Github Post-Receive commit hook

This script actually does two things:
- trigger an update of the corresponding GIT mirror repository
- send a commit mail to the mailing list
'''


from cgi import FieldStorage
from geany_commit_utils import setup_file_logging, update_repository
from json import loads
from os import unlink
from os.path import exists
import github_commit_mail
import logging
import logging.handlers


LOG_FILENAME = u'/var/log/git_mirror.log'
VALID_UPDATE_REPOSITORIES = ('geany', 'geany-plugins', 'infrastructure', 'newsletter', 'talks', 'geany-themes')
REPOSITORY_BASE_PATH = u'/srv/www/git.geany.org/repos/%s.git'
UPDATE_LOCK_FILE = u'%s/.update_lock'
UPDATE_NOTIFY_FILE = u'%s/.update_required'
# extend on demand
LOG_EMAIL_ADDRESSES = ['enrico@geany.org']


#----------------------------------------------------------------------
def setup_logging():
    logger = setup_file_logging('post_commit_hook', LOG_FILENAME)
    # mail
    mail_handler = logging.handlers.SMTPHandler(
        u'localhost',
        u'git-noreply@geany.org',
        LOG_EMAIL_ADDRESSES,
        u'Error on git_post_commit')
    mail_handler.setLevel(logging.WARNING)
    logger.addHandler(mail_handler)

    return logger


#----------------------------------------------------------------------
def handle_repository_update(repository):
    repository_path = REPOSITORY_BASE_PATH % repository
    lock_file_path = UPDATE_LOCK_FILE % repository_path
    # this is not exactly safe against race-conditions but should be good enough
    if exists(lock_file_path):
        # if there is currently an update process running, simply mark the repository to be updated
        # again later, a cronjob will pick it
        update_notify_path = UPDATE_NOTIFY_FILE % repository_path
        update_notify = open(update_notify_path, 'w')
        update_notify.write('1')
        update_notify.close()
        logger.info(u'Not updating repository %s because it is locked, leaving a notify' % repository)
    else:
        lock_file = open(lock_file_path, 'w')
        update_repository(repository, repository_path, logger)
        # remove lockfile
        lock_file.close()
        unlink(lock_file_path)


#----------------------------------------------------------------------
def process_commit_mails(content):
    user = content['repository']['owner']['name']
    repository = content['repository']['name']
    # we just use the ref here for simplicity
    branch = content['ref']
    # get a list of commit hashes
    commits = map(lambda x: x['id'], content['commits'])

    generator = github_commit_mail.CommitMailGenerator(user, repository, branch, commits, logger)
    generator.generate_commit_mails()


#----------------------------------------------------------------------
def main():
    # parse query string
    arguments = FieldStorage(keep_blank_values=True)

    json = arguments.getvalue('payload')
    content = loads(json)
    if 'commits' in content:
        repo = content['repository']['name']

        if repo in VALID_UPDATE_REPOSITORIES:
            handle_repository_update(repo)

        process_commit_mails(content)


logger = setup_logging()
try:
    main()
except Exception, e:
    logger.warn(u'An error occurred: %s' % e, exc_info=True)


print 'Content-type: text/html'
print


logging.shutdown()
