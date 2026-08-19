#!/usr/bin/env bash
set -euo pipefail

# Shared selector macro.
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/phase_interpolator/layout.tcl > /work/selector-layout.log 2>&1
sak-drc.sh -m -w /work/selector-drc /work/phase_interpolator.mag \
  > /work/selector-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/selector-lvs -s /src/phase_interpolator/phase_interpolator.spice \
  -l /work/phase_interpolator.mag -c phase_interpolator \
  > /work/selector-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n phase_interpolator_pex \
  -w /work/selector-pex /work/phase_interpolator.mag \
  > /work/selector-pex-stage.log 2>&1
cp /work/selector-drc/phase_interpolator.magic.drc/phase_interpolator.magic.drc.rpt \
  /work/selector-drc.rpt
cp /work/selector-lvs/phase_interpolator.magic.lvs/phase_interpolator.lvs.out \
  /work/selector-lvs.out
cp /work/selector-pex/phase_interpolator.pex.spice /work/phase_interpolator.pex.spice

# Nominal VCO delay tile.
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/layout.tcl > /work/vco-layout.log 2>&1
sak-drc.sh -m -w /work/vco-drc /work/cml_vco_delay.mag > /work/vco-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/vco-lvs -s /src/pll/ring_vco.spice \
  -l /work/cml_vco_delay.mag -c cml_vco_delay > /work/vco-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_vco_delay_pex \
  -w /work/vco-pex /work/cml_vco_delay.mag > /work/vco-pex-stage.log 2>&1
cp /work/vco-drc/cml_vco_delay.magic.drc/cml_vco_delay.magic.drc.rpt /work/vco-drc.rpt
cp /work/vco-lvs/cml_vco_delay.magic.lvs/cml_vco_delay.lvs.out /work/vco-lvs.out
cp /work/vco-pex/cml_vco_delay.pex.spice /work/cml_vco_delay.pex.spice

# Matched startup actuator used by each oscillator.
export VCO_CELL_NAME=cml_vco_startup_assist
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/startup_assist_layout.tcl > /work/assist-layout.log 2>&1
sak-drc.sh -m -w /work/assist-drc /work/cml_vco_startup_assist.mag \
  > /work/assist-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/assist-lvs -s /src/pll/startup_assist.spice \
  -l /work/cml_vco_startup_assist.mag -c cml_vco_startup_assist \
  > /work/assist-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_vco_startup_assist_pex \
  -w /work/assist-pex /work/cml_vco_startup_assist.mag \
  > /work/assist-pex-stage.log 2>&1
cp /work/assist-drc/cml_vco_startup_assist.magic.drc/cml_vco_startup_assist.magic.drc.rpt \
  /work/assist-drc.rpt
cp /work/assist-lvs/cml_vco_startup_assist.magic.lvs/cml_vco_startup_assist.lvs.out \
  /work/assist-lvs.out
cp /work/assist-pex/cml_vco_startup_assist.pex.spice /work/startup-assist.pex.spice

python3 /src/pll/run_selector_vco.py --source /src/pll \
  --tile-pex /work/cml_vco_delay.pex.spice \
  --assist-pex /work/startup-assist.pex.spice \
  --selector-pex /work/phase_interpolator.pex.spice \
  --work /work/composed-sim --output /work/selector-vco-simulation-result.json
python3 /src/pll/check_selector_vco.py --work /work \
  --simulation /work/selector-vco-simulation-result.json \
  --output /work/selector-vco-result.json
