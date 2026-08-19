#!/usr/bin/env bash
set -euo pipefail
cd /work

export VCO_CELL_NAME=cml_vco_delay_margin_fast
export VCO_BAND_DELAY_CELL=cml_vco_delay_margin_fast
export VCO_CAP_L=0.37
export VCO_CAP_W=3.2
export VCO_LOAD_L=4.00
export VCO_MAIN_TAIL_W=15.0
export VCO_LATCH_TAIL_W=6.0
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/layout.tcl > /work/vco-band-delay-layout.log 2>&1
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/startup_assist_layout.tcl > /work/vco-band-assist-layout.log 2>&1
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/vco_band_layout.tcl > /work/vco-band-layout.log 2>&1
python3 /src/pll/render_vco_band.py > /work/vco-band-render.log 2>&1
sak-drc.sh -m -w /work/vco-band-drc /work/cml_vco_band.mag \
  > /work/vco-band-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/vco-band-lvs -s /src/pll/vco_band.spice \
  -l /work/cml_vco_band.mag -c cml_vco_band \
  > /work/vco-band-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_vco_band_pex \
  -w /work/vco-band-pex /work/cml_vco_band.mag \
  > /work/vco-band-pex-stage.log 2>&1
cp /work/vco-band-drc/cml_vco_band.magic.drc/cml_vco_band.magic.drc.rpt \
  /work/vco-band-drc.rpt
cp /work/vco-band-lvs/cml_vco_band.magic.lvs/cml_vco_band.lvs.out \
  /work/vco-band-lvs.out
cp /work/vco-band-pex/cml_vco_band.pex.spice /work/cml-vco-band.pex.spice
# SAK emits one superfluous blank line after .ends; normalize the promoted
# artifact before hashing so it also passes the repository whitespace gate.
sed -i '${/^$/d;}' /work/cml-vco-band.pex.spice
python3 /src/pll/check_vco_band_physical.py --source /src/pll \
  --drc /work/vco-band-drc.rpt --lvs /work/vco-band-lvs.out \
  --pex /work/cml-vco-band.pex.spice --render /work/cml-vco-band-layout.png \
  --output /work/vco-band-physical-result.json
