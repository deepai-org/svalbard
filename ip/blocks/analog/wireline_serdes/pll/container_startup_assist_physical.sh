#!/usr/bin/env bash
set -euo pipefail

export VCO_CELL_NAME=cml_vco_startup_assist
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/startup_assist_layout.tcl > /work/startup-assist-layout.log 2>&1
klayout -b -r /src/render_layout.py > /work/startup-assist-render.log 2>&1
sak-drc.sh -m -w /work/startup-assist-drc /work/cml_vco_startup_assist.mag \
  > /work/startup-assist-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/startup-assist-lvs -s /src/startup_assist.spice \
  -l /work/cml_vco_startup_assist.mag -c cml_vco_startup_assist \
  > /work/startup-assist-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_vco_startup_assist_pex \
  -w /work/startup-assist-pex /work/cml_vco_startup_assist.mag \
  > /work/startup-assist-pex-stage.log 2>&1
cp /work/startup-assist-drc/cml_vco_startup_assist.magic.drc/cml_vco_startup_assist.magic.drc.rpt \
  /work/startup-assist-drc.rpt
cp /work/startup-assist-lvs/cml_vco_startup_assist.magic.lvs/cml_vco_startup_assist.lvs.out \
  /work/startup-assist-lvs.out
cp /work/startup-assist-pex/cml_vco_startup_assist.pex.spice \
  /work/startup-assist.pex.spice
grep -q '\[INFO\] COUNT: 0' /work/startup-assist-drc.rpt
grep -q 'Final result: Circuits match uniquely.' /work/startup-assist-lvs.out
grep -q '^R[0-9]' /work/startup-assist.pex.spice
grep -q '^C[0-9]' /work/startup-assist.pex.spice
