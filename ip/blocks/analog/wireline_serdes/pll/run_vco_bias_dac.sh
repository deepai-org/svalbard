#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-vco-bias-dac \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 30m --cpus 2 --memory 4g \
  --command /src/pll/container_vco_bias_dac.sh \
  --copy vco-bias-dac-result.json:vco-bias-dac-result.json \
  --copy phase_control_dac-layout.png:layout-vco-bias-dac.png
