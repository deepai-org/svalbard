#!/usr/bin/env bash
set -euo pipefail
python3 /src/pll/run_pll_clock_path_pvt.py --source /src/pll \
  --pex /src/pll/pex/pll_clock_path.pex.spice \
  --physical /src/pll/pll_clock_path_physical_result.json \
  --vco-baseline /src/pll/vco_bank_top_pvt_result.json \
  --focused-slow-res-ff --workers 8 --work /work/pll-clock-path-screen-sim \
  --output /work/pll-clock-path-screen-result.json
