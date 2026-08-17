#!/usr/bin/env bash
set -euo pipefail

ngspice -b -o /work/bias-sweep.log /src/bias_sweep_tb.spice
ngspice -b -o /work/prelayout.log /src/prelayout_tb.spice

magic -dnull -noconsole \
  -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/layout.tcl > /work/layout.log 2>&1

sak-drc.sh -m -w /work/drc /work/serdes_tx.mag > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs \
  -s /src/serdes_tx.spice \
  -l /work/serdes_tx.mag \
  -c serdes_tx > /work/lvs-stage.log 2>&1
# Preserve distributed conductor resistance down to 1 mOhm as well as coupled
# capacitance.  Zero gating thresholds force full-RC output for this small cell.
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n serdes_tx_pex -w /work/pex \
  /work/serdes_tx.mag > /work/pex-stage.log 2>&1

ngspice -b -o /work/postlayout.log /src/postlayout_tb.spice
ngspice -b -o /work/postlayout-1p25.log /src/postlayout_1p25_tb.spice
klayout -b -r /src/render_layout.py > /work/render.log 2>&1

python3 /src/check_results.py \
  --prelayout /work/prelayout.log \
  --postlayout /work/postlayout.log \
  --postlayout-1p25 /work/postlayout-1p25.log \
  --drc /work/drc/serdes_tx.magic.drc/serdes_tx.magic.drc.rpt \
  --lvs /work/lvs/serdes_tx.magic.lvs/serdes_tx.lvs.out \
  --pex /work/pex/serdes_tx.pex.spice \
  --render /work/serdes_tx-layout.png \
  --output /work/result.json
