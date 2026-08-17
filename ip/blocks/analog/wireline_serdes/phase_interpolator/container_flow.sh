#!/usr/bin/env bash
set -euo pipefail

python3 /src/run_pvt.py --source /src --work /work/schematic-pvt \
  --output /work/schematic-pvt.json --jobs 2

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/layout.tcl > /work/layout.log 2>&1
sak-drc.sh -m -w /work/drc /work/phase_interpolator.mag > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /src/phase_interpolator.spice \
  -l /work/phase_interpolator.mag -c phase_interpolator > /work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n phase_interpolator_pex -w /work/pex \
  /work/phase_interpolator.mag > /work/pex-stage.log 2>&1

pex=/work/pex/phase_interpolator.pex.spice
python3 /src/run_pvt.py --source /src --pex "$pex" --work /work/extracted-pvt \
  --output /work/extracted-pvt.json --jobs 2
python3 /src/run_robustness.py --source /src --pex "$pex" --work /work/robustness \
  --output /work/robustness.json --jobs 2
klayout -b -r /src/render_layout.py > /work/render.log 2>&1

python3 /src/check_results.py --schematic-pvt /work/schematic-pvt.json \
  --extracted-pvt /work/extracted-pvt.json --robustness /work/robustness.json \
  --drc /work/drc/phase_interpolator.magic.drc/phase_interpolator.magic.drc.rpt \
  --lvs /work/lvs/phase_interpolator.magic.lvs/phase_interpolator.lvs.out \
  --pex "$pex" --render /work/phase_interpolator-layout.png --output /work/result.json
