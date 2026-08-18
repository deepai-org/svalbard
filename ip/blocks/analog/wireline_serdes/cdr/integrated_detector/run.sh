#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cdr-integrated-detector \
  --source-rel ip/blocks/analog/wireline_serdes/cdr \
  --timeout 40m --cpus 4 --memory 6g \
  --command /src/integrated_detector/container_schematic.sh \
  --copy summary.json:cdr-integrated-detector-last.json
