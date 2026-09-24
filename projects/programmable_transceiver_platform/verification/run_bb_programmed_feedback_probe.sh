#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-bb-programmed-feedback-probe baseband/programmed_feedback_probe.py basic fresh
