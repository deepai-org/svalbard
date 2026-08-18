#!/usr/bin/env bash
set -euo pipefail

python3 /src/run_pvt.py --source /src --work /work/schematic-pvt \
  --output /work/schematic-pvt.json --jobs 4

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/layout.tcl > /work/layout.log 2>&1
sak-drc.sh -m -w /work/drc /work/cml_phase_error_filter.mag > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /src/phase_error_filter.spice \
  -l /work/cml_phase_error_filter.mag -c cml_phase_error_filter > /work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_phase_error_filter_pex -w /work/pex \
  /work/cml_phase_error_filter.mag > /work/pex-stage.log 2>&1

pex=/work/pex/cml_phase_error_filter.pex.spice
python3 /src/run_pvt.py --source /src --pex "$pex" --work /work/extracted-pvt \
  --output /work/extracted-pvt.json --jobs 4
klayout -b -r /src/render_layout.py > /work/render.log 2>&1

python3 /src/check_results.py --schematic /work/schematic-pvt.json \
  --extracted /work/extracted-pvt.json \
  --drc /work/drc/cml_phase_error_filter.magic.drc/cml_phase_error_filter.magic.drc.rpt \
  --lvs /work/lvs/cml_phase_error_filter.magic.lvs/cml_phase_error_filter.lvs.out \
  --pex "$pex" --gds /work/cml_phase_error_filter.gds \
  --render /work/cml_phase_error_filter-layout.png --output /work/result.json
