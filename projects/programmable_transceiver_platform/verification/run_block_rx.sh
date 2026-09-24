#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_rtl_check.sh" transceiver-block-rx check_block_rx.py
