#!/bin/sh
#
# Author:  Enrico Tröger
# License: GPLv2
#
# backup almost everything from Github except the GIT repositories itself as we have git.geany.org

# read the token
. /home/geany/.github-token

# start the backup
/home/geany/github-backup/venv/bin/github-backup \
    --token "${GITHUB_TOKEN}" \
    --issues \
    --issue-comments \
    --issue-events \
    --pulls \
    --pull-comments \
    --pull-commits \
    --wikis \
    --labels \
    --hooks \
    --organization \
    --milestones \
    --output-directory=/home/geany/github-backup \
    geany
