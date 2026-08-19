#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-vco-band \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 45m --cpus 2 --memory 4g --command /src/pll/container_vco_band.sh \
  --copy vco-band-result.json:vco-band-result.json \
  --copy cml-vco-band.pex.spice:cml-vco-band.pex.spice \
  --copy cml-vco-band-layout.png:layout_vco_band.png
