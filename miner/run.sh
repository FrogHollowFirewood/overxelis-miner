#!/usr/bin/env bash
set -Eeuo pipefail
cd -- "$(dirname -- "$0")"
exec /usr/bin/python3 -I -B -u ./overxelis.py "$@"
