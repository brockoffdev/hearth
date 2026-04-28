#!/bin/sh
# Hearth container entrypoint.
#
# Docker's named-volume initialization is fragile: when a fresh named volume
# mounts onto an empty directory in the image, the volume's filesystem root
# comes up owned by root regardless of what `chown` did during the image
# build.  Hearth runs as the unprivileged `hearth` user (uid 1001), so it
# can't create /data/hearth.db on first boot.
#
# This script runs as root (the image leaves USER unset), chowns /data so
# the hearth user can write to it, then re-execs the real command via gosu
# under the hearth account.  On warm starts where ownership is already
# correct the chown is a no-op.

set -e

if [ "$(id -u)" = "0" ]; then
    chown -R hearth:hearth /data 2>/dev/null || true
    exec gosu hearth "$@"
fi

exec "$@"
