#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label phase-control-dac-schematic \
  --source-rel ip/blocks/analog/wireline_serdes/phase_control_dac \
  --command /src/container_schematic.sh --timeout 10m --cpus 4 --memory 4g \
  --copy schematic-dc.json:phase-control-dac-schematic-last.json
