#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-tx-tg-dc tx/tg_dc.py wifi reuse transceiver-tx-dac-commutator-dc
