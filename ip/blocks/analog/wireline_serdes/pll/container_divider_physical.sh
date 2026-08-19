#!/usr/bin/env bash
set -euo pipefail
cd /work
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/divider_layout.tcl > /work/divider-layout.log 2>&1
sak-drc.sh -m -w /work/divider-drc /work/cml_divider_by_2.mag \
  > /work/divider-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/divider-lvs -s /src/pll/divider.spice \
  -l /work/cml_divider_by_2.mag -c cml_divider_by_2 \
  > /work/divider-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_divider_by_2_pex \
  -w /work/divider-pex /work/cml_divider_by_2.mag \
  > /work/divider-pex-stage.log 2>&1

export VCO_BAND_CELL_NAME=cml_divider_by_2
export VCO_BAND_RENDER_PATH=/work/layout-divider.png
python3 /src/pll/render_vco_band.py > /work/divider-render.log 2>&1

drc=/work/divider-drc/cml_divider_by_2.magic.drc/cml_divider_by_2.magic.drc.rpt
lvs=/work/divider-lvs/cml_divider_by_2.magic.lvs/cml_divider_by_2.lvs.out
pex=/work/divider-pex/cml_divider_by_2.pex.spice
python3 /src/pll/run_divider_schematic.py --source /src/pll --pex "$pex" \
  --work /work/divider-extracted-sim \
  --output /work/divider-extracted-result.json
python3 /src/pll/check_divider_physical.py --source /src/pll \
  --drc "$drc" --lvs "$lvs" --pex "$pex" --gds /work/cml_divider_by_2.gds \
  --render /work/layout-divider.png \
  --extracted /work/divider-extracted-result.json \
  --output /work/divider-physical-result.json
