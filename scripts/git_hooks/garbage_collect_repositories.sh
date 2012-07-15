#!/bin/bash

# Geany GIT mirror repository cleaner (executed once a week as cronjob)


REPO_HOME=/srv/www/git.geany.org/repos


cd $REPO_HOME
for repo in `ls $REPO_HOME`
do
    cd $repo

    sudo -u www-data git gc

    cd ..
done
