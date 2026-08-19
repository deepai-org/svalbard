#!/usr/bin/env bash
set -euo pipefail
export VCO_BANK_SS_ONLY=1
exec /src/container_vco_bank.sh
