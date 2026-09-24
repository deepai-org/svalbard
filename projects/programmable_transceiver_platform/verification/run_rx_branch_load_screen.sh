#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-rx-branch-load rx_branch_load_screen.py wifi_src reuse
