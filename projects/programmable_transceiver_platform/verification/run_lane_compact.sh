#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_rtl_check.sh" transceiver-lane-compact check_lane_compact.py
