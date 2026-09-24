#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-pump-branch pll/pump_branch_screen.py basic reuse transceiver-pump-device
