#!/usr/bin/env bash
set -euo pipefail

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/layout.tcl > /work/center-layout.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_vco_delay_pex -w /work/center-pex \
  /work/cml_vco_delay.mag > /work/center-pex-stage.log 2>&1

export VCO_CELL_NAME=cml_vco_delay_ss_ff
export VCO_CAP_L=0.37
export VCO_CAP_W=4.0
export VCO_LOAD_L=6.25
export VCO_MAIN_TAIL_W=15.0
export VCO_LATCH_TAIL_W=5.0
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/layout.tcl > /work/ss-ff-layout.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_vco_delay_ss_ff_pex -w /work/ss-ff-pex \
  /work/cml_vco_delay_ss_ff.mag > /work/ss-ff-pex-stage.log 2>&1

python3 /src/screen_guardband_variants.py --source /src \
  --center-pex /work/center-pex/cml_vco_delay.pex.spice \
  --ss-ff-pex /work/ss-ff-pex/cml_vco_delay_ss_ff.pex.spice \
  --work /work/guardband-screen --output /work/guardband-screen.json
