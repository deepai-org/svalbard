#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-load-terminal-dc reference/load_terminal_dc.py named_basic fresh
