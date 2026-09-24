#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-pump-control-range pll/pump_control_range_screen.py basic reuse transceiver-pump-follower
