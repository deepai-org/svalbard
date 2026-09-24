#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-pair-device-dc reference/pair_device_dc.py basic fresh
