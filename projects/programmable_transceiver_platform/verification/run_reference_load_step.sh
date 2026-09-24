#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-load-step reference/load_step_screen.py basic reuse transceiver-reference-compensation
