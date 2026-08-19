#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-vco-selector-composed \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 35m --cpus 2 --memory 4g --command /src/pll/container_selector_vco.sh \
  --copy selector-vco-result.json:cml-vco-selector-composed-last.json \
  --copy selector-vco-simulation-result.json:cml-vco-selector-composed-simulation-last.json
