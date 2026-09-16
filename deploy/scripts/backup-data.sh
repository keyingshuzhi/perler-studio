#!/usr/bin/env sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
backup_dir=${1:-"$project_root/backups"}
timestamp=$(date +%Y%m%d-%H%M%S)

mkdir -p "$backup_dir"
umask 077
tar -C "$project_root" -czf "$backup_dir/perler-studio-data-$timestamp.tar.gz" data
printf 'Backup created: %s\n' "$backup_dir/perler-studio-data-$timestamp.tar.gz"
