#!/bin/sh
# Replicator launcher: the project venv, the iGPU pin is applied inside the app before Qt loads.
cd "$(dirname "$(readlink -f "$0")")" && exec .venv/bin/python -m replicator.app "$@"
