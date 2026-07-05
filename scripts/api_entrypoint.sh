#!/bin/bash
set -e

# Ensure data directory has correct permissions
if [[ -d "/data" ]]; then
    chown -R appuser:appuser /data
fi

# Drop privileges and execute the given command
exec setpriv --reuid=appuser --regid=appuser --init-groups -- "$@"
