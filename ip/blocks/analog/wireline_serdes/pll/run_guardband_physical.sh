#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-vco-guardband-physical \
  --source-rel ip/blocks/analog/wireline_serdes/pll \
  --timeout 35m --cpus 2 --memory 4g --command /src/container_guardband_physical.sh \
  --copy cml_vco_delay_typ_margin_slow-drc.rpt:cml-vco-typ-margin-slow-drc-last.rpt \
  --copy cml_vco_delay_typ_margin_slow-lvs.out:cml-vco-typ-margin-slow-lvs-last.out \
  --copy cml_vco_delay_typ_margin_slow.pex.spice:cml-vco-typ-margin-slow-pex-last.spice \
  --copy cml_vco_delay_typ_margin_slow-layout.png:cml-vco-typ-margin-slow-layout-last.png \
  --copy typ-margin-slow-ring.json:cml-vco-typ-margin-slow-ring-last.json \
  --copy cml_vco_delay_ss_ff_margin_slow-drc.rpt:cml-vco-ss-ff-margin-slow-drc-last.rpt \
  --copy cml_vco_delay_ss_ff_margin_slow-lvs.out:cml-vco-ss-ff-margin-slow-lvs-last.out \
  --copy cml_vco_delay_ss_ff_margin_slow.pex.spice:cml-vco-ss-ff-margin-slow-pex-last.spice \
  --copy cml_vco_delay_ss_ff_margin_slow-layout.png:cml-vco-ss-ff-margin-slow-layout-last.png \
  --copy ss-ff-margin-slow-ring.json:cml-vco-ss-ff-margin-slow-ring-last.json \
  --copy cml_vco_delay_ss_ff_margin_fast-drc.rpt:cml-vco-ss-ff-margin-fast-drc-last.rpt \
  --copy cml_vco_delay_ss_ff_margin_fast-lvs.out:cml-vco-ss-ff-margin-fast-lvs-last.out \
  --copy cml_vco_delay_ss_ff_margin_fast.pex.spice:cml-vco-ss-ff-margin-fast-pex-last.spice \
  --copy cml_vco_delay_ss_ff_margin_fast-layout.png:cml-vco-ss-ff-margin-fast-layout-last.png \
  --copy ss-ff-margin-fast-ring.json:cml-vco-ss-ff-margin-fast-ring-last.json \
  --copy vco-final-margin-result.json:cml-vco-final-margin-result-last.json
