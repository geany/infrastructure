CI / Nightly-Builders
=====================

## About

Scripts and Dockerfiles for Geany and Geany-Plugins nightly builds.
`start_build.sh` will create (if missing) a Docker image for
Mingw-w64 cross-compilaton to Windows.

## Scripts and files

    ├── Dockerfile.mingw64                  -> Dockerfile for Mingw-64 build image
    ├── README.md
    ├── certificates                        -> Certificate for signing Windows binaries and installer
    │   ├── cert.pem                        -> Certificate public key (the filename is important)
    │   └── key.pem                         -> Certificate secret key (the filename is important)
    │
    ├── mingw64                             -> Helpers and configuration for Pacman and Windows builds
    │   ├── bin                                (these files will be built into the Windows Docker image)
    │   │   ├── mingw-w64-i686-wine
    │   │   └── mingw-w64-x86_64-wine
    │   └── etc
    │       ├── pacman.conf
    │       └── pacman.d
    │           └── mirrorlist.mingw64
    ├── output                              -> Directory where all build results are stored
    │
    └── start_build.sh                      -> Run Windows build containers and start builds

## Geany sources

All of the scripts can either use an existing source distribution
of Geany (and Geany-Plugins) if it is mounted into the build Docker
container (as `/geany-source` resp. `/geany-plugins-source`).
If no existing source distribution is found, the scripts will clone
Geany resp. Geany-Plugins from GIT master.

## start_build.sh

Main entry point to (re-)build the necessary Docker images and trigger
the builds of Geany and Geany-Plugins for the various targets.

    usage: start_build.sh [-m|--mingw64] [-r|--rebuild-images]
     -f, --force-rebuild     Force rebuilding of immages even if not necessary
     -g, --geany             Build Geany
    --geany-script           Path to the script to be executed to build Geany
    --geany-source           Path to a Geany source directory (optional, cloned from GIT if missing)
    --geany-plugins-script   Path to the script to be executed to build Geany-Plugins
    --geany-plugins-source   Path to a Geany-Plugins source directory (optional, cloned from GIT if missing)
     -h                      Show this help screen
     -l, --log-to-stdout     Log build output additionally to stdout
     -m, --mingw64           Build for target Mingw-w64
     -p, --geany-plugins     Build Geany-Plugins
     -r, --rebuild-images    Rebuild Docker images before start building
                             (images are rebuilt automatically every 30 days)
     -s, --sudo              Use "sudo" for Docker commands


Example to build Geany and Geany-Plugins for Windows:

    bash start_build.sh --geany --geany-plugins --mingw64

## Windows (Mingw64) build

Geany and Geany-Plugins are built for Windows by cross-compiling them in a Docker container
containing all necessary tools.

If the build was started via Github Actions from a pull request, the pull request number
will be appended to the resulting installer filename. For all other builds, the used GIT
commit short hash is used.

The created installer for Geany will contain the
[Geany-Themes](https://github.com/geany/geany-themes) collection as well as the GTK
runtime with all necessary dependencies.

The created installer for Geany-Plugins will contain all necessary dependencies
for the plugins to work.

For more details, see the scripts `scripts/ci_mingw64_geany.sh` and `build/ci_mingw64_geany_plugins.sh`
in the Geany resp. Geany-Plugins repository.

In theory, it is also possible to create release installers with this method.

### Docker image

The Docker image for the Windows build is based on a Debian image but has the full toolchain
for cross-compiling to mingw64 included. Additionally, the image contains a self-compiled
Pacman package manager to install packages from the MSYS2 repositories.

A Github Action workflow is configured in this repository to build and push the image
to the Github Docker image registry as ghcr.io/geany/geany-mingw64-ci:latest. The workflow
is triggered once a week automatically.

### Code sign certificate

If the directory `certificates` contains the two files `cert.pem` and `key.pem`,
then they will be used to digitally sign all created binary files (all built
`.exe` and `.dll` files).

If the directory is empty, code signing will be skipped.

The certificate should be in the PEM format and the key should not require a passphrase.
