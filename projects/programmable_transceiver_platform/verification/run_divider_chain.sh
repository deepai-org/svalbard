#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-divider-chain pll/divider_chain_screen.py rf_references
