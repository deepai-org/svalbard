#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-closed-loop-settling pll/closed_loop_settling_screen.py rf_chain reuse transceiver-divider-chain
