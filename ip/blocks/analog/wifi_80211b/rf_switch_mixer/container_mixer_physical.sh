#!/usr/bin/env bash
set -euo pipefail

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/rf_switch_mixer/layout.tcl > /work/layout.log 2>&1
klayout -b -r /src/rf_switch_mixer/render_layout.py > /work/render.log 2>&1
sak-drc.sh -m -w /work/drc /work/wifi_rf_switch_mixer.mag > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /src/rf_switch_mixer/mixer.spice \
  -l /work/wifi_rf_switch_mixer.mag -c wifi_rf_switch_mixer > /work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n wifi_rf_switch_mixer_pex \
  -w /work/pex /work/wifi_rf_switch_mixer.mag > /work/pex-stage.log 2>&1
pex=/work/pex/wifi_rf_switch_mixer.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
cp "$pex" /work/wifi_rf_switch_mixer.pex.spice
python3 /src/rf_switch_mixer/run_mixer.py --source /src/rf_switch_mixer \
  --pex "$pex" --work /work/mixer-cases --output /work/mixer-pex-result.json --jobs 2
python3 /src/rf_switch_mixer/check_mixer.py --result /work/mixer-pex-result.json \
  --source /src/rf_switch_mixer --pex "$pex"
printf '{"result":"pass"}\n' > /work/mixer-physical-smoke.json
