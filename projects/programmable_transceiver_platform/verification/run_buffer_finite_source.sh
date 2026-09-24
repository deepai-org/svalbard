#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-buffer-finite-source pll/buffer_finite_source_screen.py basic reuse transceiver-buffer-only-breakpoint
