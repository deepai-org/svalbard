#!/usr/bin/env bash
set -euo pipefail
runner="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../.." && pwd)/scripts/run_analog_flow.sh"
exec "$runner" --label cml-vco-startup-assist-physical \
  --source-rel ip/blocks/analog/wireline_serdes/pll \
  --timeout 20m --cpus 2 --memory 4g --command /src/container_startup_assist_physical.sh \
  --copy startup-assist-drc.rpt:cml-vco-startup-assist-drc-last.rpt \
  --copy startup-assist-lvs.out:cml-vco-startup-assist-lvs-last.out \
  --copy startup-assist.pex.spice:cml-vco-startup-assist-pex-last.spice \
  --copy cml_vco_startup_assist-layout.png:cml-vco-startup-assist-layout-last.png
