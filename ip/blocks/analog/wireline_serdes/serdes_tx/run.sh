#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label serdes-tx \
  --source-rel ip/blocks/analog/wireline_serdes/serdes_tx \
  --timeout 12m --cpus 2 --memory 4g \
  --copy result.json:serdes-tx-last.json \
  --copy serdes_tx-layout.png:serdes-tx-layout-last.png
