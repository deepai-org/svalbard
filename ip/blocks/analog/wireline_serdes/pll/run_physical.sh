#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-vco-delay-physical \
  --source-rel ip/blocks/analog/wireline_serdes/pll \
  --timeout 30m --cpus 2 --memory 4g --command /src/container_physical.sh \
  --copy drc.rpt:cml-vco-delay-drc-last.rpt \
  --copy lvs.out:cml-vco-delay-lvs-last.out \
  --copy cml_vco_delay.pex.spice:cml-vco-delay-pex-last.spice \
  --copy extracted-ring-result.json:cml-vco-delay-extracted-ring-last.json \
  --copy physical-result.json:cml-vco-delay-physical-last.json \
  --copy cml_vco_delay-layout.png:cml-vco-delay-layout-last.png
