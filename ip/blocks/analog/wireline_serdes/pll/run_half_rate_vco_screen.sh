#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-half-rate-vco-screen \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 60m --cpus 2 --memory 4g \
  --command /src/pll/container_half_rate_vco_screen.sh \
  --copy half-rate-vco-screen.json:half-rate-vco-screen.json
