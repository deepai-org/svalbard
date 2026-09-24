#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-tx-lo-switching tx/lo_switching.py wifi reuse transceiver-tx-tg-dc
