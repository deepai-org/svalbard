#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-vco-bank-top \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 45m --cpus 2 --memory 4g \
  --command /src/pll/container_vco_bank_top.sh \
  --copy vco-bank-top-physical-result.json:vco-bank-top-physical-result.json \
  --copy vco-bank-top-nominal-result.json:vco-bank-top-nominal-result.json \
  --copy vco-bank-top-pvt-result.json:vco-bank-top-pvt-result.json \
  --copy vco-bank-top-sequence-result.json:vco-bank-top-sequence-result.json \
  --copy vco-bank-top-result.json:vco-bank-top-result.json \
  --copy layout-vco-bank-top.png:layout-vco-bank-top.png
