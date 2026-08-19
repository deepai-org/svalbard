#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-vco-divider-clock-screen \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 45m --cpus 2 --memory 4g \
  --command /src/pll/container_vco_divider_clock_screen.sh \
  --copy vco-divider-composed-result.json:vco-divider-clock-screen.json
