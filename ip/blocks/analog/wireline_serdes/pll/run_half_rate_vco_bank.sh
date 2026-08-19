#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-half-rate-vco-bank \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 90m --cpus 2 --memory 4g \
  --command /src/pll/container_half_rate_vco_bank.sh \
  --copy half-rate-vco-bank-result.json:half-rate-vco-bank-result.json \
  --copy layout-half-rate-vco-bank.png:layout-half-rate-vco-bank.png
