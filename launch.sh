#!/bin/sh
# Replicator launcher (SUPER+SHIFT+H). Single instance: if it is open, focus it; otherwise start it.
# The iGPU pin is applied inside the app before Qt loads (replicator/gpu.py).
here="$(dirname "$(readlink -f "$0")")"
if [ $# -eq 0 ] && pgrep -f "python -m replicator.app" >/dev/null 2>&1; then
    exec hyprctl dispatch focuswindow "class:^(replicator)$" >/dev/null
fi
cd "$here" && exec .venv/bin/python -m replicator.app "$@"
