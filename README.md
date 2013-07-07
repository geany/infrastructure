Geany Infrastructure Scripts
============================


The scripts in this repository are used for various purposes on geany.org.

Basically they provide some additional and cool functions like announcing
GIT commits to the IRC channel, maintain the GIT mirror repository and similar tasks.


Add or remove a repository
==========================

If you want to add or remove a repository maintained by these scripts, follow these steps:

  * Edit the following files and find relevant repository information at the head of each file:
    * scripts/git2irc/git2irc.conf
    * scripts/git_hooks/github_commit_mail.py
    * scripts/git_hooks/post_commit_hook.py

  * Update the infrastructure repository on geany.org (as user *geany*):

        cd /home/geany/infrastructure && git pull

  * Edit /home/geany/git2irc.conf on geany:org: add/remove the repository from the
    "repositories" settings at the top of the file

  * Edit /usr/local/cgit/cgitrc on geany.org: at the end of the file, copy
    one of the existing repository stanzas and adjust the settings accordingly

  * Create a new GIT mirror repository (if needed): execute the following commands
    on geany.org as user *root* (and replace *geany-themes* with your repository name):

        cd /srv/www/git.geany.org/repos/
        git init --bare geany-themes.git
        cp /srv/www/git.geany.org/repos/geany.git/config /srv/www/git.geany.org/repos/geany-themes.git/
        touch /srv/www/git.geany.org/repos/geany-themes.git/.update_required
        ln -s /srv/www/git.geany.org/repos/geany-themes.git/ /srv/www/git.geany.org/git/geany-themes
        chown -R www-data:www-data /srv/www/git.geany.org/repos/geany-themes.git
        chown www-data:geany /srv/www/git.geany.org/repos/geany-themes.git
        chmod 775 /srv/www/git.geany.org/repos/geany-themes.git
        chown www-data:geany /srv/www/git.geany.org/repos/geany-themes.git/.update_required
        chmod 664 /srv/www/git.geany.org/repos/geany-themes.git/.update_required

  * Edit /srv/www/git.geany.org/repos/geany-themes.git/config and adjust remote URL

  * Execute the following commands on geany.org as user *root* to update the repository:

        cd /srv/www/git.geany.org/repos/geany-themes.git
        sudo -u www-data git remote update
        sudo -u www-data git update-server-info

  * Open http://git.geany.org/ in your browser and check whether the new repository is visible
    and has files.


IRC Bot Plugins
===============

In the directory ircbot-plugins there are two plugins for the IRC bot Supybot
(http://www.supybot.org/).

The plugins enhance the used Supybot instance on #geany by various useful and funny
features like a bunch of !commands. For details, read the source code.
