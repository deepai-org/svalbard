#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-mixed-passive pll/mixed_passive_screen.py basic reuse transceiver-pfd-pump-breakpoint
