#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-vco-band-gain-screen \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 45m --cpus 2 --memory 4g \
  --command /src/pll/container_vco_band_gain_screen.sh \
  --copy vco-band-gain-screen.json:vco-band-gain-screen.json
