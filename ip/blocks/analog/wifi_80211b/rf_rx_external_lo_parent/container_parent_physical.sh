#!/usr/bin/env bash
set -euo pipefail
cd /work
magic_run() {
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    "$1" > "$2" 2>&1
}
magic_run /src/rf_lna/layout.tcl /work/lna-layout.log
magic_run /src/rf_switch_mixer/layout.tcl /work/mixer-layout.log
magic_run /src/rf_rx_external_lo_parent/layout.tcl /work/parent-layout.log
klayout -b -r /src/rf_rx_external_lo_parent/render_layout.py > /work/render.log 2>&1
sak-drc.sh -m -w /work/drc /work/wifi_rx_external_lo_parent.mag > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /src/rf_rx_external_lo_parent/rf_rx_external_lo_parent.spice \
  -l /work/wifi_rx_external_lo_parent.mag -c wifi_rx_external_lo_parent \
  > /work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n wifi_rx_external_lo_parent_pex \
  -w /work/pex /work/wifi_rx_external_lo_parent.mag > /work/pex-stage.log 2>&1
pex=/work/pex/wifi_rx_external_lo_parent.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
cp "$pex" /work/wifi_rx_external_lo_parent.pex.spice
python3 /src/rf_rx_external_lo_parent/check_physical.py \
  --source /src/rf_rx_external_lo_parent \
  --drc /work/drc/wifi_rx_external_lo_parent.magic.drc/wifi_rx_external_lo_parent.magic.drc.rpt \
  --lvs /work/lvs/wifi_rx_external_lo_parent.magic.lvs/wifi_rx_external_lo_parent.lvs.out \
  --pex "$pex" --gds /work/wifi_rx_external_lo_parent.gds \
  --render /work/wifi-rx-external-lo-parent-layout.png \
  --output /work/parent-physical-result.json
python3 /src/rf_rx_external_lo_parent/run_parent.py --source /src/rf_rx_external_lo_parent \
  --pex "$pex" --work /work/parent-cases --output /work/parent-pex-result.json --jobs 2
python3 /src/rf_rx_external_lo_parent/check_parent.py --result /work/parent-pex-result.json \
  --physical /work/parent-physical-result.json --source /src/rf_rx_external_lo_parent --pex "$pex"
python3 /src/rf_rx_external_lo_parent/run_parent_blocker.py --source /src/rf_rx_external_lo_parent \
  --pex "$pex" --work /work/parent-blocker-cases --output /work/parent-blocker-result.json --jobs 2
python3 /src/rf_rx_external_lo_parent/check_parent_blocker.py \
  --result /work/parent-blocker-result.json --physical /work/parent-physical-result.json \
  --source /src/rf_rx_external_lo_parent --pex "$pex"
printf '{"result":"pass"}\n' > /work/parent-physical-smoke.json
