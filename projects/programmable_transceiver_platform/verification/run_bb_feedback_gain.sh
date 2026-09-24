#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-bb-feedback-gain baseband/feedback_gain_screen.py basic fresh
