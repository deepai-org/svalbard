#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-vco-ss-tune \
  --source-rel ip/blocks/analog/wireline_serdes/pll \
  --timeout 30m --cpus 2 --memory 4g --command /src/container_vco_ss_tune.sh \
  --copy cml_vco_delay_ultra_fast-drc.rpt:cml-vco-ultra-fast-drc-last.rpt \
  --copy cml_vco_delay_ultra_fast-lvs.out:cml-vco-ultra-fast-lvs-last.out \
  --copy cml_vco_delay_ultra_fast.pex.spice:cml-vco-ultra-fast-pex-last.spice \
  --copy cml_vco_delay_ultra_fast-layout.png:cml-vco-ultra-fast-layout-last.png \
  --copy ultra-fast-ring.json:cml-vco-ultra-fast-ring-last.json \
  --copy cml_vco_delay_high_gain-drc.rpt:cml-vco-high-gain-drc-last.rpt \
  --copy cml_vco_delay_high_gain-lvs.out:cml-vco-high-gain-lvs-last.out \
  --copy cml_vco_delay_high_gain.pex.spice:cml-vco-high-gain-pex-last.spice \
  --copy cml_vco_delay_high_gain-layout.png:cml-vco-high-gain-layout-last.png \
  --copy high-gain-ring.json:cml-vco-high-gain-ring-last.json
