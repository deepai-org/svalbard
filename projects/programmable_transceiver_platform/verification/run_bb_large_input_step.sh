#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-bb-large-input-step baseband/large_input_step.py paired_baseline fresh transceiver-bb-feedback-swing transceiver-bb-large-input-swing
