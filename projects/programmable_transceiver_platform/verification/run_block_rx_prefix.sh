#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_rtl_check.sh" transceiver-block-rx-prefix check_block_rx_prefix.py
