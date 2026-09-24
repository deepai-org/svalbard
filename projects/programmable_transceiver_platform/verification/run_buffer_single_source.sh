#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-buffer-single-source pll/buffer_single_source_screen.py basic reuse transceiver-buffer-only-breakpoint
