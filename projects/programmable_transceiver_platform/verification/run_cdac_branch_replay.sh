#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-cdac-branch-replay adc/cdac_branch_replay.py wifi_origin reuse transceiver-adc-reference-current
