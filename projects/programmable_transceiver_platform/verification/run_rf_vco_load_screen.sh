#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-rf-vco-load rf_vco_load_screen.py rf_sources reuse
