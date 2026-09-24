#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-pump-device pll/pump_device_screen.py basic reuse transceiver-pump-clamped
