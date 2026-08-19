#!/usr/bin/env bash
set -euo pipefail
source /src/pll/container_vco_band_physical.sh
python3 /src/pll/screen_half_rate_vco.py --source /src/pll \
  --pex /work/cml-vco-band.pex.spice --work /work/half-rate-vco-screen \
  --output /work/half-rate-vco-screen.json
