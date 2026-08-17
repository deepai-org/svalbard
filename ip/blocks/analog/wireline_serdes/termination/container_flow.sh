#!/usr/bin/env bash
set -euo pipefail

python3 /src/run_prelayout.py --source /src --work /work/prelayout --output /work/prelayout.json

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/layout.tcl > /work/layout.log 2>&1
sak-drc.sh -m -w /work/drc /work/serdes_termination.mag > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /src/termination.spice \
  -l /work/serdes_termination.mag -c serdes_termination > /work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n serdes_termination_pex -w /work/pex \
  /work/serdes_termination.mag > /work/pex-stage.log 2>&1

python3 /src/run_extracted.py --source /src --pex /work/pex/serdes_termination.pex.spice \
  --work /work/extracted --output /work/extracted.json --full-pvt
python3 /src/run_linearity.py --source /src --pex /work/pex/serdes_termination.pex.spice \
  --calibration /work/extracted.json --work /work/linearity --output /work/linearity.json
klayout -b -r /src/render_layout.py > /work/render.log 2>&1

python3 /src/check_results.py --prelayout /work/prelayout.json \
  --extracted /work/extracted.json --linearity /work/linearity.json \
  --drc /work/drc/serdes_termination.magic.drc/serdes_termination.magic.drc.rpt \
  --lvs /work/lvs/serdes_termination.magic.lvs/serdes_termination.lvs.out \
  --pex /work/pex/serdes_termination.pex.spice \
  --render /work/serdes_termination-layout.png --output /work/result.json
