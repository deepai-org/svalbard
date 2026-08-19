#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-vco-divider-composed \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 90m --cpus 2 --memory 4g \
  --command /src/pll/container_vco_divider_composed.sh \
  --copy vco-divider-composed-result.json:vco-divider-composed-result.json
