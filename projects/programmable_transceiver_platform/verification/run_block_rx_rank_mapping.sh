#!/usr/bin/env bash
set -euo pipefail
exec bash "$(dirname "$0")/run_block_rx_mapping.sh" rank
