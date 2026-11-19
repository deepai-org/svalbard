#!/bin/sh
# Chip-top regression of pt_rf (shared script ../run.sh).
exec "$(dirname "$0")/../run.sh" rf "$@"
