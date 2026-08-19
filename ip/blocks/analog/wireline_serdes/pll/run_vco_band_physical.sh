#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-vco-band-physical \
  --source-rel ip/blocks/analog/wireline_serdes \
  --timeout 35m --cpus 2 --memory 4g --command /src/pll/container_vco_band_physical.sh \
  --copy vco-band-physical-result.json:cml-vco-band-physical-last.json \
  --copy cml-vco-band.pex.spice:cml-vco-band-pex-last.spice \
  --copy cml-vco-band-layout.png:cml-vco-band-layout-last.png
