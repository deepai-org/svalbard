#!/usr/bin/env bash
set -euo pipefail
export VCO_DIVIDER_EXTRA_ARGS=--clock-width-screen
exec /src/pll/container_vco_divider_composed.sh
