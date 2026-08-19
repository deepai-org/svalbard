#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-vco-selector \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 30m --cpus 2 --memory 4g --command /src/pll/container_selector.sh \
  --copy selector-result.json:cml-vco-selector-last.json \
  --copy selector-simulation-result.json:cml-vco-selector-simulation-last.json \
  --copy phase_interpolator-layout.png:cml-vco-selector-layout-last.png
