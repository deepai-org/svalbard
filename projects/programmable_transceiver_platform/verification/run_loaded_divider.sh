#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-loaded-divider pll/loaded_divider_screen.py rf_references
