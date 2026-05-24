#!/bin/sh
set -e

_debug() {
    if [ -n "$DEBUG" ]; then
        echo "[debug] $*" >&2
    fi
}

_debug "entrypoint started"
_debug "PATH=$PATH"

PYTHON=$(command -v python3 || command -v python || true)
_debug "python binary: ${PYTHON:-NOT FOUND}"

if [ -z "$PYTHON" ]; then
    echo "[error] No python binary found on PATH. PATH=$PATH" >&2
    exit 1
fi

if [ -n "$CRON_EXPRESSION" ]; then
    _debug "CRON_EXPRESSION=$CRON_EXPRESSION"
    _debug "TZ=${TZ:-not set}"
    _debug "APPLY=${APPLY:-not set}"
    _debug "CONFIG_FILE=${CONFIG_FILE:-not set}"

    CRONTAB_FILE=/tmp/immich-crontab
    printf '%s %s -m immich_folder_organizer\n' "$CRON_EXPRESSION" "$PYTHON" > "$CRONTAB_FILE"

    _debug "crontab written to $CRONTAB_FILE:"
    if [ -n "$DEBUG" ]; then cat "$CRONTAB_FILE" >&2; fi

    exec supercronic "$CRONTAB_FILE"
else
    _debug "no CRON_EXPRESSION — one-shot run"
    _debug "APPLY=${APPLY:-not set}"
    _debug "CONFIG_FILE=${CONFIG_FILE:-not set}"
    exec "$PYTHON" -m immich_folder_organizer
fi
