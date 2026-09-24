#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_rf_loop_check.sh" vco_internal_kick "$@"
