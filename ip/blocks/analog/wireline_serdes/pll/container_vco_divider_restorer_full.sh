#!/usr/bin/env bash
set -euo pipefail
python3 /src/pll/screen_vco_divider_restorer.py --source /src/pll \
  --vco-pex /src/pll/pex/vco_bank_top.pex.spice \
  --divider-pex /src/pll/pex/divider.pex.spice \
  --restorer-pex /src/pll/pex/clock_restorer_cascade.pex.spice \
  --restorer-subckt cml_clock_restorer_cascade_pex \
  --vco-baseline /src/pll/vco_bank_top_pvt_result.json \
  --divider-physical /src/pll/divider_physical_result.json \
  --restorer-physical /src/pll/clock_restorer_cascade_physical_result.json \
  --full --workers 8 --work /work/vco-divider-restorer-full-sim \
  --output /work/vco-divider-restorer-full-result.json
