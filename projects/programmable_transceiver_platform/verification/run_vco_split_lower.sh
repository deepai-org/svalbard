#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-vco-split-lower pll/vco_split_lower.py rf_chain reuse transceiver-divider-chain
