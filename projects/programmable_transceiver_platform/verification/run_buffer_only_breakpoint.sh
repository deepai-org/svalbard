#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-buffer-only-breakpoint pll/buffer_only_breakpoint_screen.py basic reuse transceiver-pfd-only-breakpoint
