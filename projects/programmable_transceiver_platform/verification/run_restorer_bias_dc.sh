#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-restorer-bias-dc tx/restorer_bias_dc.py wifi reuse transceiver-tx-startup-state
