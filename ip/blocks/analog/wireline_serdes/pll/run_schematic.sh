#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label ring-vco-schematic \
  --source-rel ip/blocks/analog/wireline_serdes/pll \
  --timeout 60m --cpus 4 --memory 4g --command /src/container_schematic.sh \
  --copy vco-schematic-result.json:ring-vco-schematic-last.json
