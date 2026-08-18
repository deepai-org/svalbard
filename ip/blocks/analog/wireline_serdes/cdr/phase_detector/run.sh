#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cdr-phase-detector \
  --source-rel ip/blocks/analog/wireline_serdes/cdr/phase_detector \
  --timeout 150m --cpus 4 --memory 6g \
  --copy result.json:cdr-phase-detector-last.json \
  --copy cml_alexander_boundary-layout.png:cdr-phase-detector-layout-last.png
