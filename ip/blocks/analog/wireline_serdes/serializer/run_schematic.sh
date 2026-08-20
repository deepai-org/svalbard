#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label serializer-schematic \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 20m --cpus 4 --memory 6g \
  --command /src/serializer/container_schematic.sh \
  --copy serializer-schematic-result.json:serializer-schematic-result.json
