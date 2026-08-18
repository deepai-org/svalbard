#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cdr-error-slicer-schematic \
  --source-rel ip/blocks/analog/wireline_serdes/cdr/error_slicer \
  --command /src/container_schematic.sh --timeout 20m --cpus 4 --memory 6g \
  --copy schematic-pvt.json:cdr-error-slicer-schematic-last.json
