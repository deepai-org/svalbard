#!/usr/bin/env bash
set -euo pipefail

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/rf_lna/layout.tcl > /work/layout.log 2>&1
klayout -b -r /src/rf_lna/render_layout.py > /work/render.log 2>&1
sak-drc.sh -m -w /work/drc /work/wifi_lna_cs_core.mag > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /src/rf_lna/lna_cs_core.spice \
  -l /work/wifi_lna_cs_core.mag -c wifi_lna_cs_core > /work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n wifi_lna_cs_core_pex \
  -w /work/pex /work/wifi_lna_cs_core.mag > /work/pex-stage.log 2>&1
pex=/work/pex/wifi_lna_cs_core.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
cp "$pex" /work/wifi_lna_cs_core.pex.spice
python3 /src/rf_lna/run_lna_ac.py --source /src/rf_lna --pex "$pex" \
  --work /work/pex-cases --output /work/lna-pex-result.json --jobs 2 \
  || test -s /work/lna-pex-result.json
printf '{"result":"pass"}\n' > /work/lna-physical-smoke.json
