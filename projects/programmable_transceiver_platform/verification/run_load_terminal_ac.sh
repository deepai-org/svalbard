#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-load-terminal-ac-v2 reference/load_terminal_ac.py named_basic fresh
