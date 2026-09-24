#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-bb-programmed-feedback baseband/programmed_feedback_screen.py basic fresh
