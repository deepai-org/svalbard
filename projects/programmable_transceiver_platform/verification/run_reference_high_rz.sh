#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-reference-high-rz reference/measured_load_replay.py wifi_origin reuse transceiver-reference-high-rz-prepared
