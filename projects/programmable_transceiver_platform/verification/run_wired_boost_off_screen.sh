#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-wired-boost-off wired_boost_off_screen.py wired_case reuse transceiver-wired-internal
