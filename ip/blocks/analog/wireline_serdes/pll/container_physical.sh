#!/usr/bin/env bash
set -euo pipefail

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/layout.tcl > /work/layout.log 2>&1
klayout -b -r /src/render_layout.py > /work/render.log 2>&1
sak-drc.sh -m -w /work/drc /work/cml_vco_delay.mag > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /src/ring_vco.spice \
  -l /work/cml_vco_delay.mag -c cml_vco_delay > /work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_vco_delay_pex -w /work/pex \
  /work/cml_vco_delay.mag > /work/pex-stage.log 2>&1
python3 /src/run_extracted_ring.py --source /src \
  --pex /work/pex/cml_vco_delay.pex.spice --work /work/extracted-ring \
  --output /work/extracted-ring-result.json
python3 /src/check_physical.py \
  --drc /work/drc/cml_vco_delay.magic.drc/cml_vco_delay.magic.drc.rpt \
  --lvs /work/lvs/cml_vco_delay.magic.lvs/cml_vco_delay.lvs.out \
  --pex /work/pex/cml_vco_delay.pex.spice \
  --render /work/cml_vco_delay-layout.png \
  --nominal /work/extracted-ring-result.json --output /work/physical-result.json
if [[ "${RUN_VCO_PVT:-0}" == "1" ]]; then
  python3 /src/run_extracted_ring.py --source /src \
    --pex /work/pex/cml_vco_delay.pex.spice --work /work/extracted-ring-pvt \
    --output /work/extracted-ring-pvt-result.json --pvt
fi

cp /work/drc/cml_vco_delay.magic.drc/cml_vco_delay.magic.drc.rpt /work/drc.rpt
cp /work/lvs/cml_vco_delay.magic.lvs/cml_vco_delay.lvs.out /work/lvs.out
cp /work/pex/cml_vco_delay.pex.spice /work/cml_vco_delay.pex.spice
