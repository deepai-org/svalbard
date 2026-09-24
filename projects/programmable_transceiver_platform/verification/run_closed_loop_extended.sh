#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-closed-loop-extended pll/closed_loop_extended_screen.py rf_chain reuse transceiver-divider-chain
