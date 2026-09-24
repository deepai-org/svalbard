#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-vco-split-tuning pll/vco_split_tuning.py rf_chain reuse transceiver-divider-chain
