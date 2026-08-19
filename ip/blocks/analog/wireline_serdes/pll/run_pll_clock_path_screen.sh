#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label pll-clock-path-screen \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 60m --cpus 8 --memory 16g \
  --command /src/pll/container_pll_clock_path_screen.sh \
  --copy pll-clock-path-screen-result.json:pll-clock-path-screen-result.json
