#!/usr/bin/env bash
set -euo pipefail
cd /work
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/serializer/integrated_tx_layout.tcl > /work/layout.log 2>&1
sak-drc.sh -m -w /work/drc /work/serializer_tx.mag > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /src/serializer/serializer_tx.spice \
  -l /work/serializer_tx.mag -c serializer_tx > /work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n serializer_tx_pex \
  -w /work/pex /work/serializer_tx.mag > /work/pex-stage.log 2>&1
python3 /src/serializer/render_integrated_tx.py > /work/render.log 2>&1
drc=/work/drc/serializer_tx.magic.drc/serializer_tx.magic.drc.rpt
lvs=/work/lvs/serializer_tx.magic.lvs/serializer_tx.lvs.out
pex=/work/pex/serializer_tx.pex.spice
python3 /src/serializer/run_integrated_tx.py --source /src --pex "$pex" \
  --work /work/rate1 --output /work/integrated-tx-extracted-1p25.json \
  --rate 1.25e9 --jobs 4
python3 /src/serializer/run_integrated_tx.py --source /src --pex "$pex" \
  --work /work/rate2 --output /work/integrated-tx-extracted-2p5.json \
  --rate 2.5e9 --jobs 4
python3 /src/serializer/check_integrated_tx_physical.py --source /src \
  --drc "$drc" --lvs "$lvs" --pex "$pex" --gds /work/serializer_tx.gds \
  --render /work/layout-integrated-serializer-tx.png \
  --rate1 /work/integrated-tx-extracted-1p25.json \
  --rate2 /work/integrated-tx-extracted-2p5.json \
  --output /work/integrated-tx-physical-result.json
cp "$pex" /work/integrated-serializer-tx.pex.spice
