#!/usr/bin/env bash
set -euo pipefail
source /src/pll/container_vco_band_physical.sh
python3 /src/pll/screen_vco_band_gain.py --source /src/pll \
  --pex /work/cml-vco-band.pex.spice --work /work/vco-band-gain-screen \
  --output /work/vco-band-gain-screen.json
