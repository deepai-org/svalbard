#!/usr/bin/env bash
set -euo pipefail

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/rf_if_nmos_sample_switch/layout.tcl > /work/layout.log 2>&1
klayout -b -r /src/rf_if_nmos_sample_switch/render_layout.py > /work/render.log 2>&1
sak-drc.sh -m -w /work/drc /work/wifi_if_nmos_sample_switch.mag > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /src/rf_if_nmos_sample_switch/rf_if_nmos_sample_switch.spice \
  -l /work/wifi_if_nmos_sample_switch.mag -c wifi_if_nmos_sample_switch \
  > /work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n wifi_if_nmos_sample_switch_pex \
  -w /work/pex /work/wifi_if_nmos_sample_switch.mag > /work/pex-stage.log 2>&1
pex=/work/pex/wifi_if_nmos_sample_switch.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
cp "$pex" /work/wifi_if_nmos_sample_switch.pex.spice
python3 /src/rf_if_nmos_sample_switch/check_physical.py \
  --source /src/rf_if_nmos_sample_switch \
  --drc /work/drc/wifi_if_nmos_sample_switch.magic.drc/wifi_if_nmos_sample_switch.magic.drc.rpt \
  --lvs /work/lvs/wifi_if_nmos_sample_switch.magic.lvs/wifi_if_nmos_sample_switch.lvs.out \
  --pex "$pex" --gds /work/wifi_if_nmos_sample_switch.gds \
  --render /work/wifi-if-nmos-sample-switch-layout.png \
  --output /work/sample-switch-physical-result.json
python3 /src/rf_if_nmos_sample_switch/run_sampling_probe.py \
  --source /src/rf_if_nmos_sample_switch --pex "$pex" \
  --physical /work/sample-switch-physical-result.json --mode schematic \
  --work /work/sampling-schematic-cases --output /work/sample-switch-schematic-result.json --jobs 2
python3 /src/rf_if_nmos_sample_switch/run_sampling_probe.py \
  --source /src/rf_if_nmos_sample_switch --pex "$pex" \
  --physical /work/sample-switch-physical-result.json \
  --work /work/sampling-cases --output /work/sample-switch-pex-result.json --jobs 2
python3 /src/rf_if_nmos_sample_switch/check_nmos_rejection.py \
  --physical /work/sample-switch-physical-result.json \
  --schematic /work/sample-switch-schematic-result.json \
  --pex-result /work/sample-switch-pex-result.json --pex "$pex" \
  --output /work/sample-switch-rejection-result.json
printf '{"result":"pass"}\n' > /work/sample-switch-physical-smoke.json
