#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-lna-mixer lna_mixer_screen.py wifi_src reuse
