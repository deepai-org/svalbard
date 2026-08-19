#!/usr/bin/env bash
set -euo pipefail
cd /work
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/clock_restorer_layout.tcl > /work/clock-restorer-leaf-layout.log 2>&1
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/clock_restorer_cascade_layout.tcl > /work/clock-restorer-cascade-layout.log 2>&1
sak-drc.sh -m -w /work/clock-restorer-cascade-drc /work/cml_clock_restorer_cascade.mag \
  > /work/clock-restorer-cascade-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/clock-restorer-cascade-lvs -s /src/pll/clock_restorer_cascade.spice \
  -l /work/cml_clock_restorer_cascade.mag -c cml_clock_restorer_cascade \
  > /work/clock-restorer-cascade-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_clock_restorer_cascade_pex \
  -w /work/clock-restorer-cascade-pex /work/cml_clock_restorer_cascade.mag \
  > /work/clock-restorer-cascade-pex-stage.log 2>&1
export VCO_BAND_CELL_NAME=cml_clock_restorer_cascade
export VCO_BAND_RENDER_PATH=/work/layout-clock-restorer-cascade.png
python3 /src/pll/render_vco_band.py > /work/clock-restorer-cascade-render.log 2>&1
drc=/work/clock-restorer-cascade-drc/cml_clock_restorer_cascade.magic.drc/cml_clock_restorer_cascade.magic.drc.rpt
lvs=/work/clock-restorer-cascade-lvs/cml_clock_restorer_cascade.magic.lvs/cml_clock_restorer_cascade.lvs.out
pex=/work/clock-restorer-cascade-pex/cml_clock_restorer_cascade.pex.spice
python3 /src/pll/check_clock_restorer_physical.py --source /src/pll \
  --drc "$drc" --lvs "$lvs" --pex "$pex" \
  --gds /work/cml_clock_restorer_cascade.gds \
  --render /work/layout-clock-restorer-cascade.png \
  --claim clock_restorer_cascade_structural_physical_closure \
  --layout-source clock_restorer_cascade_layout.tcl \
  --schematic-source clock_restorer_cascade.spice \
  --minimum-resistors 40 --minimum-capacitors 10 \
  --output /work/clock-restorer-cascade-physical-result.json
cp "$pex" /work/clock-restorer-cascade.pex.spice
