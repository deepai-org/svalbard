#!/usr/bin/env bash
set -euo pipefail

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/rf_nfet_array_coupon/layout.tcl > /work/layout.log 2>&1
klayout -b -r /src/rf_nfet_array_coupon/render_layout.py > /work/render.log 2>&1
sak-drc.sh -m -w /work/drc /work/wifi_rf_nfet_array_coupon.mag > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs -s /src/rf_nfet_array_coupon/rf_nfet_array_coupon.spice \
  -l /work/wifi_rf_nfet_array_coupon.mag -c wifi_rf_nfet_array_coupon > /work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n wifi_rf_nfet_array_coupon_pex \
  -w /work/pex /work/wifi_rf_nfet_array_coupon.mag > /work/pex-stage.log 2>&1
pex=/work/pex/wifi_rf_nfet_array_coupon.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
cp "$pex" /work/wifi_rf_nfet_array_coupon.pex.spice
python3 /src/rf_nfet_array_coupon/check_physical.py --source /src/rf_nfet_array_coupon \
  --drc /work/drc/wifi_rf_nfet_array_coupon.magic.drc/wifi_rf_nfet_array_coupon.magic.drc.rpt \
  --lvs /work/lvs/wifi_rf_nfet_array_coupon.magic.lvs/wifi_rf_nfet_array_coupon.lvs.out \
  --pex "$pex" --gds /work/wifi_rf_nfet_array_coupon.gds \
  --render /work/wifi-rf-nfet-array-coupon-layout.png --output /work/coupon-physical-result.json
python3 /src/rf_nfet_array_coupon/run_coupon.py --source /src/rf_nfet_array_coupon --pex "$pex" \
  --work /work/coupon-cases --output /work/coupon-pex-result.json --jobs 2
python3 /src/rf_nfet_array_coupon/check_coupon.py --result /work/coupon-pex-result.json \
  --physical /work/coupon-physical-result.json --source /src/rf_nfet_array_coupon --pex "$pex"
printf '{"result":"pass"}\n' > /work/coupon-physical-smoke.json
