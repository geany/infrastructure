#!/bin/bash
#
# Copyright 2022 The Geany contributors
# License: GPLv2
#
# Run Windows build containers and start builds within.
# The Docker image for the containers are rebuilt automatically
# every 30 days to keep them up to date.
#
# This script has to be run outside of the containers.
#
# usage: start_build.sh [-m|--mingw64] [-r|--rebuild-images]
#  -f, --force-rebuild     Force rebuilding of immages even if not necessary
#  -g, --geany             Build Geany
# --geany-source           Path to a Geany source directory (optional, cloned from GIT if missing)
# --geany-plugins-source   Path to a Geany-Plugins source directory (optional, cloned from GIT if missing)
#  -h                      Show this help screen
#  -l, --log-to-stdout     Log build output additionally to stdout
#  -m, --mingw64           Build for target Mingw-w64
#  -p, --geany-plugins     Build Geany-Plugins
#  -r, --rebuild-images    Rebuild Docker images before start building
#                          (images are rebuilt automatically every 30 days)
#  -s, --sudo              Use "sudo" for Docker commands


DOCKER_IMAGE_MAX_AGE_DAYS=30

BASE_OUTPUT_DIRECTORY="${PWD}/output/"
DOCKER_CMD="docker"
GEANY_BUILD_SCRIPT=/geany-source/scripts/ci_mingw64_geany.sh
GEANY_SOURCE=
GEANY_PLUGINS_BUILD_SCRIPT=/geany-plugins-source/build/ci_mingw64_geany_plugins.sh
GEANY_PLUGINS_SOURCE=

# stop on errors
set -e
set -o pipefail


log() {
	log_filename="$1"
	shift
	if [ "${log_filename}" = "-" ]; then
		echo "========== $(date '+%Y-%m-%d %H:%M:%S %Z') $@ =========="
	else
		if [ -n "${DO_LOG_TO_STDOUT}" ]; then
			$@ 2>&1 | tee "${log_filename}"
		else
			$@ > "${log_filename}" 2>&1
		fi
	fi
}


rebuild_image() {
	image_name="$1"
	dockerfile="$2"
	build_args="$3"
	# query image created date or use 0 if the image does not exist to trigger a build
	image_date=$(${DOCKER_CMD} image inspect --format='{{.Created}}' "${image_name}" 2>/dev/null || echo -n 1970-01-01)
	image_date=$(echo "${image_date}" | xargs) # trim leading and trailing whitespace
	image_date_seconds=$(date --date="${image_date}" "+%s")
	expire_date_seconds=$(date --date="${DOCKER_IMAGE_MAX_AGE_DAYS} days ago" "+%s")
	if [ "${image_date_seconds}" -lt "${expire_date_seconds}" ] || [ -n "${DO_FORCE_IMAGE_REBUILD}" ]; then
		log - "Building image ${image_name} (last build: ${image_date})"
		log "${BASE_OUTPUT_DIRECTORY}/docker_image_build_${image_name}_$(date '+%Y_%m_%d_%H_%M_%S').log" \
			${DOCKER_CMD} build \
				--no-cache \
				--file "${dockerfile}" \
				--label "org.opencontainers.image.created=$(date --iso-8601=seconds)" \
				--tag "${image_name}" \
				${build_args} \
				.
	fi
}


build_mingw64() {
	IMAGE_NAME_WINDOWS="geany-mingw64-ci"
	MINGW64_OUTPUT_DIRECTORY=${BASE_OUTPUT_DIRECTORY}/mingw64
	LOGFILE_MINGW64_GEANY=${MINGW64_OUTPUT_DIRECTORY}/build_mingw64_geany_$(date '+%Y_%m_%d_%H_%M_%S').log
	LOGFILE_MINGW64_GEANY_PLUGINS=${MINGW64_OUTPUT_DIRECTORY}/build_mingw64_geany_plugins_$(date '+%Y_%m_%d_%H_%M_%S').log
	mkdir -p "${MINGW64_OUTPUT_DIRECTORY}"

	# (re)build Docker image
	rebuild_image ${IMAGE_NAME_WINDOWS} Dockerfile.mingw64

	# Build Geany
	if [ -n "${DO_GEANY}" ]; then
		log - "Building Geany for Windows"
		if [ -n "${GEANY_SOURCE}" ]; then
			source_volume="--volume ${GEANY_SOURCE}:/geany-source/:ro"
		else
			source_volume=
		fi
		log "${LOGFILE_MINGW64_GEANY}" \
			${DOCKER_CMD} run \
				--rm \
				--env=GITHUB_PULL_REQUEST="${GITHUB_PULL_REQUEST}" \
				--env=CI="${CI}" \
				--env=JOBS="${JOBS}" \
				${source_volume} \
				--volume "${PWD}/scripts:/scripts/" \
				--volume "${PWD}/certificates/:/certificates/" \
				--volume "${MINGW64_OUTPUT_DIRECTORY}:/output/" \
				"${IMAGE_NAME_WINDOWS}:latest" \
				bash ${GEANY_BUILD_SCRIPT}
	fi

	# Build Geany-Plugins
	if [ -n "${DO_GEANY_PLUGINS}" ]; then
		log - "Building Geany-Plugins for Windows"
		if [ -n "${GEANY_PLUGINS_SOURCE}" ]; then
			source_volume="--volume ${GEANY_PLUGINS_SOURCE}:/geany-plugins-source/:ro"
		else
			source_volume=
		fi
		log "${LOGFILE_MINGW64_GEANY_PLUGINS}" \
			${DOCKER_CMD} run \
				--rm \
				--env=GITHUB_PULL_REQUEST="${GITHUB_PULL_REQUEST}" \
				--env=CI="${CI}" \
				--env=JOBS="${JOBS}" \
				${source_volume} \
				--volume "${PWD}/scripts:/scripts/" \
				--volume "${PWD}/certificates/:/certificates/" \
				--volume "${MINGW64_OUTPUT_DIRECTORY}:/output/" \
				"${IMAGE_NAME_WINDOWS}:latest" \
				bash ${GEANY_PLUGINS_BUILD_SCRIPT}
	fi
}


usage() {
	echo "usage: start_build.sh [-m|--mingw64]"
	echo "                      [-r|--rebuild-images]"
	echo " -g, --geany             Build Geany"
	echo "--geany-script           Path to the script to be executed to build Geany"
	echo "--geany-source           Path to a Geany source directory (optional, cloned from GIT if missing)"
	echo "--geany-plugins-script   Path to the script to be executed to build Geany-Plugins"
	echo "--geany-plugins-source   Path to a Geany-Plugins source directory (optional, cloned from GIT if missing)"
	echo " -h                      Show this help screen"
	echo " -l, --log-to-stdout     Log build output additionally to stdout"
	echo " -m, --mingw64           Build for target Mingw-w64"
	echo " -p, --geany-plugins     Build Geany-Plugins"
	echo " -r, --rebuild-images    Rebuild Docker images before start building"
	echo "                         (images are rebuilt automatically every ${DOCKER_IMAGE_MAX_AGE_DAYS} days)"
	echo " -s, --sudo              Use \"sudo\" for Docker commands"
	exit 1
}


parse_command_line_options() {
	if [ $# -eq 0 ]; then
		usage
	fi
	for opt in "$@"; do
		case "$opt" in
			-f|--force-rebuild)
			DO_FORCE_IMAGE_REBUILD=1
			shift
			;;
			-g|--geany)
			DO_GEANY=1
			shift
			;;
			--geany-script)
			GEANY_BUILD_SCRIPT="${2}"
			shift
			shift
			;;
			--geany-source)
			GEANY_SOURCE="${2}"
			shift
			shift
			;;
			--geany-plugins-script)
			GEANY_PLUGINS_BUILD_SCRIPT="${2}"
			shift
			shift
			;;
			--geany-plugins-source)
			GEANY_PLUGINS_SOURCE="${2}"
			shift
			shift
			;;
			-l|--log-to-stdout)
			DO_LOG_TO_STDOUT=1
			shift
			;;
			-m|--mingw64)
			DO_MINGW64=1
			shift
			;;
			-p|--geany-plugins)
			DO_GEANY_PLUGINS=1
			shift
			;;
			-r|--rebuild-images)
			DO_IMAGE_REBUILD=1
			shift
			;;
			-s|--sudo)
			DOCKER_CMD="sudo docker"
			shift
			;;
			-h|--help)
			usage
			;;
		esac
	done
}


DO_MINGW64=
DO_IMAGE_REBUILD=
DO_FORCE_IMAGE_REBUILD=
DO_GEANY=
DO_GEANY_PLUGINS=
DO_LOG_TO_STDOUT=
GEANY_SOURCE=
GEANY_PLUGINS_SOURCE=


main() {
	if [ -n "${DO_MINGW64}" ]; then
		build_mingw64
	fi
}


parse_command_line_options $@
main
