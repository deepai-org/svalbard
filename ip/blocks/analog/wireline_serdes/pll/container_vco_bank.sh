#!/usr/bin/env bash
set -euo pipefail

variants=(fast ultra_fast slow high_gain)
cap_lengths=(0.6 0.5 2.4 0.5)
load_lengths=(5.25 4.25 5.25 6.5)
if [[ "${VCO_BANK_SS_ONLY:-0}" == "1" ]]; then
  variants=(ultra_fast high_gain)
  cap_lengths=(0.5 0.5)
  load_lengths=(4.25 6.5)
fi

for index in "${!variants[@]}"; do
  variant="${variants[$index]}"
  cell="cml_vco_delay_${variant}"
  export VCO_CELL_NAME="$cell"
  export VCO_CAP_L="${cap_lengths[$index]}"
  export VCO_LOAD_L="${load_lengths[$index]}"
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    /src/layout.tcl > "/work/${cell}-layout.log" 2>&1
  klayout -b -r /src/render_layout.py > "/work/${cell}-render.log" 2>&1
  sak-drc.sh -m -w "/work/${cell}-drc" "/work/${cell}.mag" \
    > "/work/${cell}-drc-stage.log" 2>&1
  sak-lvs.sh -m -w "/work/${cell}-lvs" -s /src/physical_variants.spice \
    -l "/work/${cell}.mag" -c "$cell" > "/work/${cell}-lvs-stage.log" 2>&1
  sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n "${cell}_pex" \
    -w "/work/${cell}-pex" "/work/${cell}.mag" \
    > "/work/${cell}-pex-stage.log" 2>&1
  cp "/work/${cell}-drc/${cell}.magic.drc/${cell}.magic.drc.rpt" \
    "/work/${cell}-drc.rpt"
  cp "/work/${cell}-lvs/${cell}.magic.lvs/${cell}.lvs.out" \
    "/work/${cell}-lvs.out"
  cp "/work/${cell}-pex/${cell}.pex.spice" "/work/${cell}.pex.spice"
done

if [[ "${VCO_BANK_SS_ONLY:-0}" != "1" ]]; then
python3 /src/run_extracted_ring.py --source /src \
  --pex /work/cml_vco_delay_slow.pex.spice --pex-subckt cml_vco_delay_slow_pex \
  --work /work/slow-ring --output /work/slow-ring.json --environment-index 1 || true
python3 /src/run_extracted_ring.py --source /src \
  --pex /work/cml_vco_delay_fast.pex.spice --pex-subckt cml_vco_delay_fast_pex \
  --work /work/fast-ring --output /work/fast-ring.json --environment-index 2 || true
fi
python3 /src/run_extracted_ring.py --source /src \
  --pex /work/cml_vco_delay_ultra_fast.pex.spice --pex-subckt cml_vco_delay_ultra_fast_pex \
  --work /work/ultra-fast-ring --output /work/ultra-fast-ring.json --environment-index 4 \
  --control 1.30 --control 1.40 --control 1.50 --control 1.65 --control 1.80 \
  --control 2.00 --control 2.20 || true
python3 /src/run_extracted_ring.py --source /src \
  --pex /work/cml_vco_delay_high_gain.pex.spice --pex-subckt cml_vco_delay_high_gain_pex \
  --work /work/high-gain-ring --output /work/high-gain-ring.json --environment-index 3 \
  --control 1.30 --control 1.40 --control 1.50 --control 1.65 --control 1.80 \
  --control 2.00 --control 2.20 || true
if [[ "${VCO_BANK_SS_ONLY:-0}" != "1" ]]; then
  python3 /src/check_vco_bank.py --source /src --work /work \
    --output /work/vco-bank-result.json
else
  python3 - <<'PY'
import json
from pathlib import Path
results = [json.loads(Path(path).read_text())["result"] for path in
           ("/work/ultra-fast-ring.json", "/work/high-gain-ring.json")]
if results != ["pass", "pass"]:
    raise SystemExit("SS tuning candidates do not yet cover both targets")
PY
fi
