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

# Verify python3 can actually execute (catches missing shared libs after apt autoremove)
_debug "python3 exec test: $($PYTHON --version 2>&1 || echo 'FAILED — binary exists but cannot execute')"

# Verify /bin/sh exists — supercronic runs all jobs via /bin/sh -c
_debug "sh: $(ls -la /bin/sh 2>&1 || echo 'NOT FOUND')"
_debug "sh exec test: $(/bin/sh -c 'echo ok' 2>&1 || echo 'FAILED — /bin/sh cannot execute')"

# Verify supercronic itself (wrong-arch binary would print garbage or fail)
_debug "supercronic version: $(supercronic -version 2>&1 | head -1 || echo 'FAILED to invoke supercronic')"

if [ -n "$CRON_EXPRESSION" ]; then
    _debug "CRON_EXPRESSION=$CRON_EXPRESSION"
    _debug "TZ=${TZ:-not set}"
    _debug "APPLY=${APPLY:-not set}"
    _debug "CONFIG_FILE=${CONFIG_FILE:-not set}"

    CRONTAB_FILE=/tmp/immich-crontab
    printf '%s %s -m immich_folder_organizer\n' "$CRON_EXPRESSION" "$PYTHON" > "$CRONTAB_FILE"

    _debug "crontab written to $CRONTAB_FILE:"
    if [ -n "$DEBUG" ]; then cat "$CRONTAB_FILE" >&2; fi

    # -no-reap: workaround for supercronic v0.2.33 zombie reaper crashing at
    #           startup with "Failed to fork exec: no such file or directory"
    #           when running as pid 1. The cron job (python) exits cleanly so
    #           we don't need zombie reaping.
    # -passthrough-logs: print job stdout/stderr directly instead of wrapping
    #           each line in a supercronic INFO log entry.
    exec supercronic -no-reap -passthrough-logs "$CRONTAB_FILE"
else
    _debug "no CRON_EXPRESSION — one-shot run"
    _debug "APPLY=${APPLY:-not set}"
    _debug "CONFIG_FILE=${CONFIG_FILE:-not set}"
    exec "$PYTHON" -m immich_folder_organizer
fi
