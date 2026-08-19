#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-vco-band-bank \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 120m --cpus 2 --memory 4g --command /src/pll/container_vco_band_bank.sh \
  --copy vco-band-bank-result.json:vco-band-bank-result.json \
  --copy layout-vco-band-bank.png:layout-vco-band-bank.png
