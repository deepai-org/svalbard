#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-pump-follower pll/pump_follower_screen.py basic reuse transceiver-pump-dummy-impedance
