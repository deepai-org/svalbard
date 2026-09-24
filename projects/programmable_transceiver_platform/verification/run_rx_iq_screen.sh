#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-rx-iq rx_iq_screen.py wifi_src reuse
