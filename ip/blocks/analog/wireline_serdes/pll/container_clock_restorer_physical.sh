#!/usr/bin/env bash
set -euo pipefail
cd /work
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/clock_restorer_layout.tcl > /work/clock-restorer-layout.log 2>&1
sak-drc.sh -m -w /work/clock-restorer-drc /work/cml_clock_restorer.mag \
  > /work/clock-restorer-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/clock-restorer-lvs -s /src/pll/clock_restorer.spice \
  -l /work/cml_clock_restorer.mag -c cml_clock_restorer \
  > /work/clock-restorer-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_clock_restorer_pex \
  -w /work/clock-restorer-pex /work/cml_clock_restorer.mag \
  > /work/clock-restorer-pex-stage.log 2>&1
export VCO_BAND_CELL_NAME=cml_clock_restorer
export VCO_BAND_RENDER_PATH=/work/layout-clock-restorer.png
python3 /src/pll/render_vco_band.py > /work/clock-restorer-render.log 2>&1
drc=/work/clock-restorer-drc/cml_clock_restorer.magic.drc/cml_clock_restorer.magic.drc.rpt
lvs=/work/clock-restorer-lvs/cml_clock_restorer.magic.lvs/cml_clock_restorer.lvs.out
pex=/work/clock-restorer-pex/cml_clock_restorer.pex.spice
python3 /src/pll/check_clock_restorer_physical.py --source /src/pll \
  --drc "$drc" --lvs "$lvs" --pex "$pex" --gds /work/cml_clock_restorer.gds \
  --render /work/layout-clock-restorer.png \
  --output /work/clock-restorer-physical-result.json
cp "$pex" /work/clock-restorer.pex.spice
