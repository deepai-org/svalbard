#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-vco-capture-tuning pll/vco_capture_tuning.py rf_chain reuse transceiver-divider-chain
