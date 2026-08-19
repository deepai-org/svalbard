#!/usr/bin/env bash
set -euo pipefail

# Rebuild the shared phase-interpolator geometry in its strict selector role.
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
cp /work/selector-pex/phase_interpolator.pex.spice \
  /work/phase_interpolator.pex.spice
klayout -b -r /src/phase_interpolator/render_layout.py \
  > /work/selector-render.log 2>&1

python3 /src/pll/run_selector.py --source /src/pll \
  --pex /work/phase_interpolator.pex.spice --work /work/selector-sim \
  --output /work/selector-simulation-result.json
python3 /src/pll/check_selector.py --source /src --work /work \
  --simulation /work/selector-simulation-result.json \
  --output /work/selector-result.json
