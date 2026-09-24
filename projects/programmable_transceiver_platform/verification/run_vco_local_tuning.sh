#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-vco-local-tuning pll/vco_local_tuning.py rf_references
