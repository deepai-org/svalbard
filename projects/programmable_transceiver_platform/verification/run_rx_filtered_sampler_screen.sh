#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-rx-filtered-sampler rx_filtered_sampler_screen.py wifi_src reuse
