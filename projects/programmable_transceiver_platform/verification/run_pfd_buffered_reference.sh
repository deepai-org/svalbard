#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_rf_loop_check.sh" pfd_buffered_reference "$@"
