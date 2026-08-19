#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-half-rate-vco-full-bank \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 150m --cpus 2 --memory 4g \
  --command /src/pll/container_half_rate_vco_full_bank.sh \
  --copy half-rate-vco-full-bank-result.json:half-rate-vco-full-bank-result.json \
  --copy split_base-control-vco-full-screen.json:split_base-control-vco-full-screen.json \
  --copy split_fast-control-vco-full-screen.json:split_fast-control-vco-full-screen.json \
  --copy split_gain-control-vco-full-screen.json:split_gain-control-vco-full-screen.json
