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

import logging
from os import listdir, unlink
from os.path import exists, join

from geany_commit_utils import setup_file_logging, update_repository

LOG_FILENAME = '/var/log/git_mirror.log'
REPOSITORY_BASE_PATH = '/srv/www/git.geany.org/repos/'
UPDATE_LOCK_FILE = '%s/_geany/.update_lock'
UPDATE_NOTIFY_FILE = '%s/_geany/.update_required'


def setup_logging():
    logger_ = setup_file_logging('update_repositories', LOG_FILENAME)
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(name)s: %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger_.addHandler(handler)

    return logger_


def handle_repository_update(repository):
    repository_path = join(REPOSITORY_BASE_PATH, repository)
    lock_file_path = UPDATE_LOCK_FILE % repository_path
    update_notify_path = UPDATE_NOTIFY_FILE % repository_path
    # this is not exactly safe against race-conditions but should be good enough
    if exists(lock_file_path):
        return

    if exists(update_notify_path):
        with open(update_notify_path, 'r+', encoding='utf-8') as update_notify_file:
            need_update = update_notify_file.read() == '1'
            if need_update:
                with open(lock_file_path, 'w', encoding='utf-8'):
                    update_repository(repository, repository_path, logger, run_as='www-data')
                    unlink(lock_file_path)
                # unmark update notify
                update_notify_file.truncate(0)


def main():
    repositories = listdir(REPOSITORY_BASE_PATH)
    for repository in repositories:
        handle_repository_update(repository)


if __name__ == '__main__':
    logger = setup_logging()
    try:
        main()
    except Exception as exc:
        logger.warning('An error occurred: %s', str(exc), exc_info=True)
    logging.shutdown()
