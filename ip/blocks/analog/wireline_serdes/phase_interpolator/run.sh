#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label phase-interpolator \
  --source-rel ip/blocks/analog/wireline_serdes/phase_interpolator \
  --timeout 180m --cpus 2 --memory 4g \
  --copy result.json:phase-interpolator-last.json \
  --copy phase_interpolator-layout.png:phase-interpolator-layout-last.png
