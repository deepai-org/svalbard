#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_rtl_check.sh" transceiver-block-elastic check_block_elastic.py
