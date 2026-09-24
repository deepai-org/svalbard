#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-tx-dac-commutator-dc tx/dac_commutator_dc.py wifi reuse transceiver-dac-segmented-dc
