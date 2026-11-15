#!/bin/sh
# Replicator launcher: ./launch.sh [program.json | model.glb | bundle.zip]
# With no argument and Replicator already open under Hyprland, focus that window instead of starting another.
here="$(dirname "$(readlink -f "$0")")"
if [ $# -eq 0 ] && command -v hyprctl >/dev/null 2>&1 && pgrep -f "python -m replicator.app" >/dev/null 2>&1; then
    exec hyprctl dispatch focuswindow "class:^(replicator)$" >/dev/null
fi
py="$here/.venv/bin/python"
[ -x "$py" ] || py="$(command -v python3)"
cd "$here" && exec "$py" -m replicator.app "$@"
