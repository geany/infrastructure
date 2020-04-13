#!/bin/sh
#
# Author:  Enrico Tröger
# License: GPLv2
#
# backup almost everything from Github except the GIT repositories itself as we have git.geany.org


# start the backup
/home/geany/github-backup/venv/bin/github-backup \
    --token file:///home/geany/.github-token \
    --issues \
    --issue-comments \
    --issue-events \
    --pulls \
    --pull-comments \
    --pull-commits \
    --releases \
    --wikis \
    --labels \
    --milestones \
    --hooks \
    --organization \
    --output-directory=/home/geany/github-backup \
    geany
