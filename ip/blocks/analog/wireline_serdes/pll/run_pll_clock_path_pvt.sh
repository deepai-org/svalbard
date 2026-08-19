#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label pll-clock-path-pvt \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 90m --cpus 8 --memory 16g \
  --command /src/pll/container_pll_clock_path_pvt.sh \
  --copy pll-clock-path-pvt-result.json:pll-clock-path-pvt-result.json
