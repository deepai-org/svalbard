#!/usr/bin/env bash
set -euo pipefail

variants=(fast ultra_fast slow high_gain ss_ff ss_ss margin_slow margin_fast \
  typ_margin_slow ss_ff_margin_slow ss_ff_margin_fast)
cap_lengths=(0.6 0.5 2.4 0.5 0.37 0.38 0.50 0.37 0.85 0.40 0.37)
cap_widths=(4.0 4.0 4.0 4.0 4.0 4.0 4.0 3.2 4.0 4.0 3.2)
load_lengths=(5.25 4.25 5.25 6.5 6.25 4.00 4.00 4.00 5.25 6.25 6.25)
main_tail_widths=(10.0 10.0 10.0 10.0 15.0 15.0 15.0 15.0 10.0 15.0 15.0)
latch_tail_widths=(4.0 4.0 4.0 4.0 5.0 6.0 6.0 6.0 4.0 5.0 5.0)

for index in "${!variants[@]}"; do
  variant="${variants[$index]}"
  cell="cml_vco_delay_${variant}"
  export VCO_CELL_NAME="$cell"
  export VCO_CAP_L="${cap_lengths[$index]}"
  export VCO_CAP_W="${cap_widths[$index]}"
  export VCO_LOAD_L="${load_lengths[$index]}"
  export VCO_MAIN_TAIL_W="${main_tail_widths[$index]}"
  export VCO_LATCH_TAIL_W="${latch_tail_widths[$index]}"
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

python3 /src/run_extracted_ring.py --source /src \
  --pex /work/cml_vco_delay_slow.pex.spice --pex-subckt cml_vco_delay_slow_pex \
  --work /work/slow-ring --output /work/slow-ring.json --environment-index 1 || true
python3 /src/run_extracted_ring.py --source /src \
  --pex /work/cml_vco_delay_fast.pex.spice --pex-subckt cml_vco_delay_fast_pex \
  --work /work/fast-ring --output /work/fast-ring.json --environment-index 2 || true
python3 /src/run_extracted_ring.py --source /src \
  --pex /work/cml_vco_delay_ss_ff.pex.spice --pex-subckt cml_vco_delay_ss_ff_pex \
  --work /work/ss-ff-ring --output /work/ss-ff-ring.json --environment-index 3 \
  --control 1.15 --control 1.20 --control 1.25 --control 1.30 --control 1.35 --control 1.40 || true
python3 /src/run_extracted_ring.py --source /src \
  --pex /work/cml_vco_delay_ss_ss.pex.spice --pex-subckt cml_vco_delay_ss_ss_pex \
  --work /work/ss-ss-ring --output /work/ss-ss-ring.json --environment-index 4 \
  --control 1.15 --control 1.20 --control 1.25 --control 1.30 --control 1.35 --control 1.40 || true
python3 /src/run_extracted_ring.py --source /src \
  --pex /work/cml_vco_delay_margin_slow.pex.spice --pex-subckt cml_vco_delay_margin_slow_pex \
  --work /work/margin-slow-ring --output /work/margin-slow-ring.json --pvt \
  --control 0.88 --control 0.98 --control 1.08 --control 1.15 --control 1.18 \
  --control 1.20 --control 1.25 --control 1.30 --control 1.35 --control 1.40 --control 1.50 || true
python3 /src/run_extracted_ring.py --source /src \
  --pex /work/cml_vco_delay_margin_fast.pex.spice --pex-subckt cml_vco_delay_margin_fast_pex \
  --work /work/margin-fast-ring --output /work/margin-fast-ring.json --pvt \
  --control 0.88 --control 0.98 --control 1.08 --control 1.15 --control 1.18 \
  --control 1.20 --control 1.25 --control 1.30 --control 1.35 --control 1.40 --control 1.50 || true
controls=(--control 0.88 --control 0.98 --control 1.08 --control 1.15 \
  --control 1.18 --control 1.20 --control 1.25 --control 1.30 \
  --control 1.35 --control 1.40 --control 1.50)
python3 /src/run_extracted_ring.py --source /src \
  --pex /work/cml_vco_delay_typ_margin_slow.pex.spice \
  --pex-subckt cml_vco_delay_typ_margin_slow_pex \
  --work /work/typ-margin-slow-ring --output /work/typ-margin-slow-ring.json \
  --environment-index 0 "${controls[@]}" || true
python3 /src/run_extracted_ring.py --source /src \
  --pex /work/cml_vco_delay_ss_ff_margin_slow.pex.spice \
  --pex-subckt cml_vco_delay_ss_ff_margin_slow_pex \
  --work /work/ss-ff-margin-slow-ring --output /work/ss-ff-margin-slow-ring.json \
  --environment-index 3 "${controls[@]}" || true
python3 /src/run_extracted_ring.py --source /src \
  --pex /work/cml_vco_delay_ss_ff_margin_fast.pex.spice \
  --pex-subckt cml_vco_delay_ss_ff_margin_fast_pex \
  --work /work/ss-ff-margin-fast-ring --output /work/ss-ff-margin-fast-ring.json \
  --environment-index 3 "${controls[@]}" || true
python3 /src/check_vco_bank.py --source /src --work /work \
  --output /work/vco-bank-result.json
python3 /src/compose_layout_bank.py --source /src --work /work \
  --output /work/layout-vco-bank.png
