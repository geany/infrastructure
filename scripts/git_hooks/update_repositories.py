#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Author:  Enrico Tröger
# License: GPLv2
#
'''
Geany GIT mirror repository updater

This script is called automatically every 5 minutes as cronjob or can be run manually
to update all of the Geany GIT Github mirror repositories which were marked by the
post_commit_hook script to be out-of-date.
'''

from geany_commit_utils import setup_file_logging, update_repository
from os import listdir, unlink
from os.path import exists, join
import logging


LOG_FILENAME = u'/var/log/git_mirror.log'
REPOSITORY_BASE_PATH = u'/srv/www/git.geany.org/repos/'
UPDATE_LOCK_FILE = u'%s/.update_lock'
UPDATE_NOTIFY_FILE = u'%s/.update_required'


#----------------------------------------------------------------------
def setup_logging():
    logger = setup_file_logging('update_repositories', LOG_FILENAME)
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(name)s: %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


#----------------------------------------------------------------------
def handle_repository_update(repository):
    repository_path = join(REPOSITORY_BASE_PATH, repository)
    lock_file_path = UPDATE_LOCK_FILE % repository_path
    update_notify_path = UPDATE_NOTIFY_FILE % repository_path
    # this is not exactly safe against race-conditions but should be good enough
    if exists(lock_file_path):
        return

    if exists(update_notify_path):
        update_notify_file = open(update_notify_path, 'r+')
        need_update = update_notify_file.read() == '1'
        if need_update:
            lock_file = open(lock_file_path, 'w')
            update_repository(repository, repository_path, logger, run_as='www-data')
            # remove lockfile
            lock_file.close()
            unlink(lock_file_path)
            # unmark update notify
            update_notify_file.truncate(0)
            update_notify_file.close()


#----------------------------------------------------------------------
def main():
    repositories = listdir(REPOSITORY_BASE_PATH)
    for repository in repositories:
        handle_repository_update(repository)


logger = setup_logging()
try:
    main()
except Exception, e:
    logger.warn(u'An error occurred: %s' % e, exc_info=True)

logging.shutdown()
