#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-pfd-event-offset pll/pfd_event_offset_screen.py basic reuse transceiver-pfd-matched-waveform
