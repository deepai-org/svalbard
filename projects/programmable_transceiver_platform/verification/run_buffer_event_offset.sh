#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-buffer-event-offset pll/buffer_event_offset_screen.py basic reuse transceiver-buffer-finite-source
