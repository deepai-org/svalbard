#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-pump-steering-phase pll/pump_steering_phase_screen.py basic reuse transceiver-pump-steering
