#!/bin/sh
# Production container entrypoint.
#
# A Render persistent disk is mounted when the container starts, so the
# image's build-time chown never applies to it, and files copied onto it
# (e.g. by scp) arrive root-owned. Fix ownership of the embedded Chroma
# directory as root, then drop to the non-root appuser to run the app.
set -e

if [ "$(id -u)" = "0" ]; then
  if [ "${CHROMA_MODE:-http}" = "embedded" ] && [ -n "${CHROMA_PERSIST_DIRECTORY:-}" ]; then
    mkdir -p "$CHROMA_PERSIST_DIRECTORY"
    chown -R appuser:appuser "$CHROMA_PERSIST_DIRECTORY"
  fi
  export HOME=/home/appuser
  exec setpriv --reuid=appuser --regid=appuser --init-groups "$@"
fi

exec "$@"
