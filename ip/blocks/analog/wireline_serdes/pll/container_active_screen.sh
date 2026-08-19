#!/usr/bin/env bash
set -euo pipefail

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/layout.tcl > /work/layout.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_vco_delay_pex -w /work/pex \
  /work/cml_vco_delay.mag > /work/pex-stage.log 2>&1
python3 /src/screen_active_variants.py --source /src \
  --pex /work/pex/cml_vco_delay.pex.spice --work /work/active-screen \
  --output /work/active-screen.json
