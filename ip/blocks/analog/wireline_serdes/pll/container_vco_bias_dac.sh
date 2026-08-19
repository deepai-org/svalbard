#!/usr/bin/env bash
set -euo pipefail
cd /work

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/phase_control_dac/layout.tcl > /work/vco-bias-dac-layout.log 2>&1
sak-drc.sh -m -w /work/vco-bias-dac-drc /work/phase_control_dac.mag \
  > /work/vco-bias-dac-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/vco-bias-dac-lvs \
  -s /src/phase_control_dac/phase_control_dac.spice \
  -l /work/phase_control_dac.mag -c phase_control_dac \
  > /work/vco-bias-dac-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n phase_control_dac_pex \
  -w /work/vco-bias-dac-pex /work/phase_control_dac.mag \
  > /work/vco-bias-dac-pex-stage.log 2>&1
python3 /src/phase_control_dac/render_layout.py > /work/vco-bias-dac-render.log 2>&1

drc=/work/vco-bias-dac-drc/phase_control_dac.magic.drc/phase_control_dac.magic.drc.rpt
lvs=/work/vco-bias-dac-lvs/phase_control_dac.magic.lvs/phase_control_dac.lvs.out
pex=/work/vco-bias-dac-pex/phase_control_dac.pex.spice
python3 /src/pll/run_vco_bias_dac.py --source /src/pll --pex "$pex" \
  --work /work/vco-bias-dac-sim --output /work/vco-bias-dac-simulation.json
python3 /src/pll/check_vco_bias_dac.py --source /src/pll \
  --dac-source /src/phase_control_dac \
  --simulation /work/vco-bias-dac-simulation.json \
  --drc "$drc" --lvs "$lvs" --pex "$pex" \
  --gds /work/phase_control_dac.gds \
  --render /work/phase_control_dac-layout.png \
  --output /work/vco-bias-dac-result.json
