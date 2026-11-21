#!/usr/bin/env bash
set -euo pipefail
# Native Wayland/X11 Qt 6 launcher for Cron Manager
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-wayland;xcb}"
exec python3 "$(dirname "$(readlink -f "$0")")/gui.py" "$@"
