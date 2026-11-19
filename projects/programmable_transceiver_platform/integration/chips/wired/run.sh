#!/bin/sh
# Chip-top regression of pt_wired (shared script ../run.sh).
exec "$(dirname "$0")/../run.sh" wired "$@"
