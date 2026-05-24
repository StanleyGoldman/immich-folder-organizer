#!/bin/sh
set -e

if [ -n "$CRON_EXPRESSION" ]; then
    # Write supercronic crontab and exec in place
    CRONTAB_FILE=/tmp/immich-crontab
    printf '%s python -m immich_folder_organizer\n' "$CRON_EXPRESSION" > "$CRONTAB_FILE"
    exec supercronic "$CRONTAB_FILE"
else
    # One-shot run
    exec python -m immich_folder_organizer
fi
