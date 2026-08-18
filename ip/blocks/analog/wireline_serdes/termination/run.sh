#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label serdes-termination \
  --source-rel ip/blocks/analog/wireline_serdes/termination \
  --timeout 20m --cpus 2 --memory 4g \
  --copy result.json:serdes-termination-last.json \
  --copy serdes_termination-layout.png:serdes-termination-layout-last.png
