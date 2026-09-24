#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-pfd-only-breakpoint pll/pfd_only_breakpoint_screen.py basic reuse transceiver-pfd-buffered-reference
