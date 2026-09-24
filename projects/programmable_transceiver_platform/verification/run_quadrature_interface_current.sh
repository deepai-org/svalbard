#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-quadrature-interface-current quadrature/interface_current.py baseline_wifi reuse transceiver-quadrature-lna-final
