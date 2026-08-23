#!/usr/bin/env bash
set -euo pipefail
cd /work
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/data_restorer/stage_layout.tcl > /work/data-restorer-stage-layout.log 2>&1
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/data_restorer/layout.tcl > /work/data-restorer-layout.log 2>&1
sak-drc.sh -m -w /work/data-restorer-drc /work/cml_data_restorer.mag \
  > /work/data-restorer-drc.log 2>&1
sak-lvs.sh -m -w /work/data-restorer-lvs -s /src/data_restorer/data_restorer.spice \
  -l /work/cml_data_restorer.mag -c cml_data_restorer \
  > /work/data-restorer-lvs.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_data_restorer_pex \
  -w /work/data-restorer-pex /work/cml_data_restorer.mag \
  > /work/data-restorer-pex.log 2>&1
export VCO_BAND_CELL_NAME=cml_data_restorer
export VCO_BAND_RENDER_PATH=/work/layout-data-restorer.png
python3 /src/pll/render_vco_band.py > /work/data-restorer-render.log 2>&1
drc=/work/data-restorer-drc/cml_data_restorer.magic.drc/cml_data_restorer.magic.drc.rpt
lvs=/work/data-restorer-lvs/cml_data_restorer.magic.lvs/cml_data_restorer.lvs.out
pex=/work/data-restorer-pex/cml_data_restorer.pex.spice
python3 /src/pll/check_clock_restorer_physical.py --source /src/data_restorer \
  --drc "$drc" --lvs "$lvs" --pex "$pex" --gds /work/cml_data_restorer.gds \
  --render /work/layout-data-restorer.png \
  --claim data_restorer_structural_physical_closure \
  --layout-source layout.tcl --schematic-source data_restorer.spice \
  --minimum-resistors 40 --minimum-capacitors 10 \
  --output /work/data-restorer-physical-result.json
cp "$pex" /work/data-restorer.pex.spice
