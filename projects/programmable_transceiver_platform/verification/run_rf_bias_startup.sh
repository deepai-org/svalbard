#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-rf-bias-startup rf_bias_startup_screen.py rf_references
