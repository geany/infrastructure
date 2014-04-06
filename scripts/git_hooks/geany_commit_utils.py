# -*- coding: utf-8 -*-
#
# Author:  Enrico Tröger
# License: GPLv2
#
'''
Utility functions for the Geany GIT hook/mirror scripts
'''


from subprocess import Popen, PIPE
import logging


#----------------------------------------------------------------------
def setup_file_logging(name, logfile):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler(logfile)
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s %(name)s: %(levelname)s: %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


#----------------------------------------------------------------------
def run_command(repository_path, command, redirect_stdout=None, run_as=None, logger=None):
    if run_as:
        command = ('sudo', '-u', run_as) + command
    process = Popen(command, cwd=repository_path, stdout=PIPE, stderr=PIPE)
    stdout, stderr = process.communicate()
    output = u''
    if stdout:
        output = u'%s\nStdout:\n%s' % (output, stdout)
        if redirect_stdout:
            target_file = open(redirect_stdout, 'w')
            target_file.write(stdout)
            target_file.close()
    if stderr:
        output = u'%s\nStderr:\n%s' % (output, stderr)
    if logger:
        exit_code = process.returncode
        logger.debug(u'Command "%s" exited with code %s: %s' % (' '.join(command), exit_code, output))


#----------------------------------------------------------------------
def update_repository(repository, repository_path, logger, run_as=None):
    logger.info(u'Updating repository %s' % repository)
    run_command(repository_path, ('git', 'remote', 'update'), run_as=run_as, logger=logger)
    run_command(repository_path, ('git', 'update-server-info'), run_as=run_as, logger=logger)
    run_command(repository_path,
                ('git', 'log', '--max-count=1', '--format="%cd"', '--date=local'),
                redirect_stdout='%s/_geany/cgit_age' % repository_path,
                logger=logger)
