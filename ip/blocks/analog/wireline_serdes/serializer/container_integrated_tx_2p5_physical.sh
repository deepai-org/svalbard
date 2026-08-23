#!/usr/bin/env bash
set -euo pipefail

export SERIALIZER_TX_CELL=serializer_tx_2p5
export SERIALIZER_TX_TAIL_LENGTH=0.28
export SERIALIZER_TX_BOOST_LOADS=1
export INTEGRATED_TX_GDS=/work/serializer_tx_2p5.gds
export INTEGRATED_TX_RENDER=/work/layout-integrated-serializer-tx-2p5.png
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/serializer/integrated_tx_layout.tcl > /work/layout.log 2>&1
sak-drc.sh -m -w /work/drc /work/serializer_tx_2p5.mag > /work/drc.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /src/serializer/serializer_tx_2p5.spice \
  -l /work/serializer_tx_2p5.mag -c serializer_tx_2p5 > /work/lvs.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n serializer_tx_pex \
  -w /work/pex /work/serializer_tx_2p5.mag > /work/pex.log 2>&1
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' \
  /work/pex/serializer_tx_2p5.pex.spice
grep -q '^\* PEX produced using ' /work/pex/serializer_tx_2p5.pex.spice
python3 /src/serializer/render_integrated_tx.py > /work/render.log 2>&1
python3 /src/serializer/check_integrated_tx_2p5_physical.py \
  --drc /work/drc/serializer_tx_2p5.magic.drc/serializer_tx_2p5.magic.drc.rpt \
  --lvs /work/lvs/serializer_tx_2p5.magic.lvs/serializer_tx_2p5.lvs.out \
  --pex /work/pex/serializer_tx_2p5.pex.spice \
  --gds /work/serializer_tx_2p5.gds \
  --render /work/layout-integrated-serializer-tx-2p5.png \
  --layout /src/serializer/integrated_tx_layout.tcl \
  --schematic /src/serializer/serializer_tx_2p5.spice \
  --output /work/integrated-tx-2p5-physical-result.json
cp /work/pex/serializer_tx_2p5.pex.spice \
  /work/integrated-serializer-tx-2p5.pex.spice
