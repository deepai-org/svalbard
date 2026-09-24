#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-bb-noise-receiver-cm baseband/noise_receiver_cm.py basic fresh
