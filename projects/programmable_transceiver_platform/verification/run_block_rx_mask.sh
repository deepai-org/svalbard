#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_rtl_check.sh" transceiver-block-rx-mask check_block_rx_mask.py
