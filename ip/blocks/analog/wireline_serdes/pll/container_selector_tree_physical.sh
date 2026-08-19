#!/usr/bin/env bash
set -euo pipefail

cd /work
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/phase_interpolator/layout.tcl > /work/pi-layout-regression.log 2>&1
sak-drc.sh -m -w /work/pi-drc-regression /work/phase_interpolator.mag \
  > /work/pi-drc-regression-stage.log 2>&1
sak-lvs.sh -m -w /work/pi-lvs-regression \
  -s /src/phase_interpolator/phase_interpolator.spice \
  -l /work/phase_interpolator.mag -c phase_interpolator \
  > /work/pi-lvs-regression-stage.log 2>&1
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/selector_unit_layout.tcl > /work/tree-leaf-layout.log 2>&1
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/selector_tree_layout.tcl > /work/tree-layout.log 2>&1
klayout -b -r /src/pll/render_selector_tree.py > /work/tree-render.log 2>&1
sak-drc.sh -m -w /work/tree-drc /work/vco_selector_tree.mag \
  > /work/tree-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/tree-lvs -s /src/pll/selector_tree.spice \
  -l /work/vco_selector_tree.mag -c vco_selector_tree \
  > /work/tree-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n vco_selector_tree_pex \
  -w /work/tree-pex /work/vco_selector_tree.mag \
  > /work/tree-pex-stage.log 2>&1
cp /work/tree-drc/vco_selector_tree.magic.drc/vco_selector_tree.magic.drc.rpt \
  /work/tree-drc.rpt
cp /work/tree-lvs/vco_selector_tree.magic.lvs/vco_selector_tree.lvs.out \
  /work/tree-lvs.out
cp /work/tree-pex/vco_selector_tree.pex.spice /work/vco-selector-tree.pex.spice
python3 /src/pll/check_selector_tree_physical.py --source /src/pll \
  --drc /work/tree-drc.rpt --lvs /work/tree-lvs.out \
  --pex /work/vco-selector-tree.pex.spice \
  --render /work/vco-selector-tree-layout.png \
  --output /work/selector-tree-physical-result.json
