#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_analog_check.sh" transceiver-quadrature-buffered-transient quadrature/buffered_transient.py basic reuse transceiver-quadrature-rc-buffered
