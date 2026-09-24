#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-pump-steering pll/pump_steering_screen.py basic reuse transceiver-pump-branch
