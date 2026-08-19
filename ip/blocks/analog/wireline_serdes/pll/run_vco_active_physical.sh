#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-vco-active-physical \
  --source-rel ip/blocks/analog/wireline_serdes/pll \
  --timeout 35m --cpus 2 --memory 4g --command /src/container_vco_active_physical.sh \
  --copy cml_vco_delay_ss_ff-drc.rpt:cml-vco-ss-ff-drc-last.rpt \
  --copy cml_vco_delay_ss_ff-lvs.out:cml-vco-ss-ff-lvs-last.out \
  --copy cml_vco_delay_ss_ff.pex.spice:cml-vco-ss-ff-pex-last.spice \
  --copy cml_vco_delay_ss_ff-layout.png:cml-vco-ss-ff-layout-last.png \
  --copy ss-ff-ring.json:cml-vco-ss-ff-ring-last.json \
  --copy cml_vco_delay_ss_ss-drc.rpt:cml-vco-ss-ss-drc-last.rpt \
  --copy cml_vco_delay_ss_ss-lvs.out:cml-vco-ss-ss-lvs-last.out \
  --copy cml_vco_delay_ss_ss.pex.spice:cml-vco-ss-ss-pex-last.spice \
  --copy cml_vco_delay_ss_ss-layout.png:cml-vco-ss-ss-layout-last.png \
  --copy ss-ss-ring.json:cml-vco-ss-ss-ring-last.json
