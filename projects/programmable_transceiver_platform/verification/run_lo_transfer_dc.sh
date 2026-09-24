#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-lo-transfer-dc-v2 quadrature/lo_transfer_dc.py basic fresh
