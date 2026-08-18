#!/usr/bin/env bash
set -euo pipefail
python3 /src/run_pvt.py --source /src --work /work/schematic-pvt --output /work/schematic-pvt.json --jobs 4
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" /src/layout.tcl > /work/layout.log 2>&1
sak-drc.sh -m -w /work/drc /work/cml_error_slicer.mag > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /src/error_slicer.spice -l /work/cml_error_slicer.mag -c cml_error_slicer > /work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_error_slicer_pex -w /work/pex /work/cml_error_slicer.mag > /work/pex-stage.log 2>&1
pex=/work/pex/cml_error_slicer.pex.spice
python3 /src/run_pvt.py --source /src --pex "$pex" --work /work/extracted-pvt --output /work/extracted-pvt.json --jobs 4
klayout -b -r /src/render_layout.py > /work/render.log 2>&1
python3 /src/check_results.py --schematic /work/schematic-pvt.json --extracted /work/extracted-pvt.json \
  --drc /work/drc/cml_error_slicer.magic.drc/cml_error_slicer.magic.drc.rpt \
  --lvs /work/lvs/cml_error_slicer.magic.lvs/cml_error_slicer.lvs.out \
  --pex "$pex" --gds /work/cml_error_slicer.gds --render /work/cml_error_slicer-layout.png --output /work/result.json
