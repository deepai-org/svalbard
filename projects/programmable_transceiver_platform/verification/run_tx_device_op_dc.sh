#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-tx-device-op-dc tx/device_op_dc.py wifi reuse transceiver-tx-common-mode-dc
