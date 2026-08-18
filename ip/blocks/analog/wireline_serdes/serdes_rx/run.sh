#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label serdes-rx \
  --source-rel ip/blocks/analog/wireline_serdes/serdes_rx \
  --timeout 180m --cpus 2 --memory 4g \
  --copy result.json:serdes-rx-last.json \
  --copy serdes_rx-layout.png:serdes-rx-layout-last.png
