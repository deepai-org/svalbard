#!/usr/bin/env bash
set -euo pipefail

python3 /src/run_boundary_pvt.py --source /src --work /work/schematic-pvt \
  --output /work/schematic-pvt.json --jobs 4

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/layout.tcl > /work/layout.log 2>&1
sak-drc.sh -m -w /work/drc /work/cml_alexander_boundary.mag > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /src/cml_phase_detector.spice \
  -l /work/cml_alexander_boundary.mag -c cml_alexander_boundary > /work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_alexander_boundary_pex -w /work/pex \
  /work/cml_alexander_boundary.mag > /work/pex-stage.log 2>&1

pex=/work/pex/cml_alexander_boundary.pex.spice
python3 /src/run_boundary_pvt.py --source /src --pex "$pex" --work /work/extracted-pvt \
  --output /work/extracted-pvt.json --jobs 4
python3 /src/run_boundary_stress.py --source /src --pex "$pex" \
  --pvt /work/extracted-pvt.json --work /work/stress --output /work/stress.json --jobs 4
klayout -b -r /src/render_layout.py > /work/render.log 2>&1

python3 /src/check_results.py --schematic-pvt /work/schematic-pvt.json \
  --extracted-pvt /work/extracted-pvt.json --stress /work/stress.json \
  --drc /work/drc/cml_alexander_boundary.magic.drc/cml_alexander_boundary.magic.drc.rpt \
  --lvs /work/lvs/cml_alexander_boundary.magic.lvs/cml_alexander_boundary.lvs.out \
  --pex "$pex" --render /work/cml_alexander_boundary-layout.png --output /work/result.json
