#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label pll-clock-path-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 40m --cpus 4 --memory 8g \
  --command /src/pll/container_pll_clock_path_physical.sh \
  --copy pll-clock-path-physical-result.json:pll-clock-path-physical-result.json \
  --copy pll-clock-path.pex.spice:pll-clock-path.pex.spice \
  --copy layout-pll-clock-path.png:layout-pll-clock-path.png
