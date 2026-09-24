#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-tx-common-mode-dc tx/common_mode_dc.py wifi reuse transceiver-tx-dac-commutator-dc
