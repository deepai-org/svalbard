#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-divider-schematic \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 20m --cpus 2 --memory 4g \
  --command /src/pll/container_divider_schematic.sh \
  --copy divider-schematic-result.json:divider-schematic-result.json
