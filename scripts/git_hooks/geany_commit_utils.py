# -*- coding: utf-8 -*-
#
# Author:  Enrico Tröger
# License: GPLv2
#

'''
Utility functions for the Geany GIT hook/mirror scripts
'''

import logging
from subprocess import PIPE, Popen


def setup_file_logging(name, logfile):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler(logfile)
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(name)s: %(levelname)s: %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def run_command(repository_path, command, redirect_stdout=None, run_as=None, logger=None):
    if run_as:
        command = ('sudo', '-u', run_as) + command
    with Popen(command, cwd=repository_path, stdout=PIPE, stderr=PIPE) as process:
        stdout, stderr = process.communicate()
        output = ''
        if stdout:
            stdout = stdout.decode('utf-8')
            output = f'{output}\nStdout:\n{stdout}'
            if redirect_stdout:
                with open(redirect_stdout, 'w', encoding='utf-8') as target_file:
                    target_file.write(stdout)

        if stderr:
            stderr = stderr.decode('utf-8')
            output = f'{output}\nStderr:\n{stderr}'
        if logger:
            exit_code = process.returncode
            logger.debug('Command "%s" exited with code %s: %s', ' '.join(command), exit_code, output)


def update_repository(repository, repository_path, logger, run_as=None):
    logger.info(f'Updating repository {repository}')
    run_command(repository_path, ('git', 'remote', 'update'), run_as=run_as, logger=logger)
    run_command(repository_path, ('git', 'update-server-info'), run_as=run_as, logger=logger)
    run_command(repository_path,
                ('git', 'log', '--max-count=1', '--format="%cd"', '--date=local'),
                redirect_stdout=f'{repository_path}/_geany/cgit_age',
                logger=logger)
