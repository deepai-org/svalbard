#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-wired-internal wired_internal_screen.py wired_case reuse transceiver-wired-phase-200ps
