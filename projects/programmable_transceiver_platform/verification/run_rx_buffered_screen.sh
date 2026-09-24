#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-rx-buffered rx_buffered_screen.py wifi_src reuse
