#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-bb-large-input-swing baseband/feedback_swing_screen.py basic fresh transceiver-bb-large-input-gain
