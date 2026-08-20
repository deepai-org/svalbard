#!/usr/bin/env bash
set -euo pipefail
cd /work
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/serializer/layout.tcl > /work/layout.log 2>&1
sak-drc.sh -m -w /work/drc /work/cml_serializer_2to1.mag \
  > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /src/serializer/serializer.spice \
  -l /work/cml_serializer_2to1.mag -c cml_serializer_2to1 \
  > /work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_serializer_2to1_pex \
  -w /work/pex /work/cml_serializer_2to1.mag \
  > /work/pex-stage.log 2>&1
python3 /src/serializer/render_layout.py > /work/render.log 2>&1

drc=/work/drc/cml_serializer_2to1.magic.drc/cml_serializer_2to1.magic.drc.rpt
lvs=/work/lvs/cml_serializer_2to1.magic.lvs/cml_serializer_2to1.lvs.out
pex=/work/pex/cml_serializer_2to1.pex.spice
python3 /src/serializer/run_composed.py --source /src --pex "$pex" \
  --work /work/extracted-sim --output /work/serializer-extracted-result.json --jobs 4
python3 /src/serializer/run_composed.py --source /src --pex "$pex" \
  --work /work/stress-sim --output /work/serializer-2p5g-result.json \
  --jobs 4 --rate 2.5e9
python3 /src/serializer/check_physical.py --source /src --drc "$drc" \
  --lvs "$lvs" --pex "$pex" --gds /work/cml_serializer_2to1.gds \
  --render /work/layout-serializer.png \
  --extracted /work/serializer-extracted-result.json \
  --stress /work/serializer-2p5g-result.json \
  --output /work/serializer-physical-result.json
cp "$pex" /work/serializer.pex.spice
