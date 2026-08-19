#!/usr/bin/env bash
set -euo pipefail
cd /work

variants=(hr_gain hr_gain_fast hr_4p5 hr_4p75 hr_4p8 hr_5p8 hr_11p0)
cap_lengths=(3.45 3.2 4.5 4.75 4.8 5.8 11.0)
cap_widths=(4.0 4.0 3.2 3.2 3.2 3.3 3.2)
load_lengths=(6.5 6.5 4.0 4.0 4.0 4.0 4.0)
main_tail_widths=(10.0 10.0 15.0 15.0 15.0 15.0 15.0)
latch_tail_widths=(4.0 4.0 6.0 6.0 6.0 6.0 6.0)

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/startup_assist_layout.tcl > /work/half-rate-assist-layout.log 2>&1

for index in "${!variants[@]}"; do
  variant="${variants[$index]}"
  delay_cell="cml_vco_delay_${variant}"
  band_cell="cml_vco_band_${variant}"
  export VCO_CELL_NAME="$delay_cell"
  export VCO_CAP_L="${cap_lengths[$index]}"
  export VCO_CAP_W="${cap_widths[$index]}"
  export VCO_LOAD_L="${load_lengths[$index]}"
  export VCO_MAIN_TAIL_W="${main_tail_widths[$index]}"
  export VCO_LATCH_TAIL_W="${latch_tail_widths[$index]}"
  export VCO_BAND_DELAY_CELL="$delay_cell"
  export VCO_BAND_CELL_NAME="$band_cell"
  export VCO_BAND_RENDER_PATH="/work/${band_cell}-layout.png"
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    /src/pll/layout.tcl > "/work/${delay_cell}-layout.log" 2>&1
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    /src/pll/vco_band_layout.tcl > "/work/${band_cell}-layout.log" 2>&1
  python3 /src/pll/render_vco_band.py > "/work/${band_cell}-render.log" 2>&1
  sak-drc.sh -m -w "/work/${band_cell}-drc" "/work/${band_cell}.mag" \
    > "/work/${band_cell}-drc-stage.log" 2>&1
  sak-lvs.sh -m -w "/work/${band_cell}-lvs" \
    -s /src/pll/half_rate_vco_variants.spice \
    -l "/work/${band_cell}.mag" -c "$band_cell" \
    > "/work/${band_cell}-lvs-stage.log" 2>&1
  sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n "${band_cell}_pex" \
    -w "/work/${band_cell}-pex" "/work/${band_cell}.mag" \
    > "/work/${band_cell}-pex-stage.log" 2>&1
  cp "/work/${band_cell}-drc/${band_cell}.magic.drc/${band_cell}.magic.drc.rpt" \
    "/work/${band_cell}-drc.rpt"
  cp "/work/${band_cell}-lvs/${band_cell}.magic.lvs/${band_cell}.lvs.out" \
    "/work/${band_cell}-lvs.out"
  cp "/work/${band_cell}-pex/${band_cell}.pex.spice" \
    "/work/${band_cell}.pex.spice"
  sed -i '${/^$/d;}' "/work/${band_cell}.pex.spice"
done

python3 /src/pll/compose_vco_band_bank.py --work /work \
  --variants "${variants[@]}" --title "GF180MCU 1.25 GHz folded VCO parents — emitted-GDS renders" \
  --output /work/layout-half-rate-vco-bank.png
python3 /src/pll/run_vco_band_bank.py --source /src/pll --pex-dir /work \
  --variants "${variants[@]}" --target-hz 1.25e9 --guardband-fraction 0.02 \
  --qualification required_target \
  --claim complete_parent_pex_half_rate_vco_bank \
  --work /work/half-rate-vco-bank-sim \
  --output /work/half-rate-vco-bank-simulation.json
python3 /src/pll/check_vco_band_bank.py --source /src/pll --work /work \
  --variants "${variants[@]}" --claim seven_complete_physical_half_rate_vco_parents \
  --qualification required_target \
  --schematic-source half_rate_vco_variants.spice \
  --delay-schematic-source half_rate_vco_variants.spice \
  --simulation /work/half-rate-vco-bank-simulation.json \
  --render /work/layout-half-rate-vco-bank.png \
  --output /work/half-rate-vco-bank-result.json
