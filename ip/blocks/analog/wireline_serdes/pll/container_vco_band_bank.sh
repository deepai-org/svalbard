#!/usr/bin/env bash
set -euo pipefail
cd /work

variants=(center fast ultra_fast slow high_gain ss_ff ss_ss margin_slow margin_fast \
  typ_margin_slow ss_ff_margin_slow ss_ff_margin_fast)
cap_lengths=(0.8 0.6 0.5 2.4 0.5 0.37 0.38 0.50 0.37 0.85 0.40 0.37)
cap_widths=(4.0 4.0 4.0 4.0 4.0 4.0 4.0 4.0 3.2 4.0 4.0 3.2)
load_lengths=(5.25 5.25 4.25 5.25 6.5 6.25 4.00 4.00 4.00 5.25 6.25 6.25)
main_tail_widths=(10.0 10.0 10.0 10.0 10.0 15.0 15.0 15.0 15.0 10.0 15.0 15.0)
latch_tail_widths=(4.0 4.0 4.0 4.0 4.0 5.0 6.0 6.0 6.0 4.0 5.0 5.0)

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/startup_assist_layout.tcl > /work/band-bank-assist-layout.log 2>&1

for index in "${!variants[@]}"; do
  variant="${variants[$index]}"
  if [[ "$variant" == center ]]; then
    delay_cell=cml_vco_delay
  else
    delay_cell="cml_vco_delay_${variant}"
  fi
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
    /src/pll/layout.tcl > "/work/${delay_cell}-band-layout.log" 2>&1
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    /src/pll/vco_band_layout.tcl > "/work/${band_cell}-layout.log" 2>&1
  python3 /src/pll/render_vco_band.py > "/work/${band_cell}-render.log" 2>&1
  sak-drc.sh -m -w "/work/${band_cell}-drc" "/work/${band_cell}.mag" \
    > "/work/${band_cell}-drc-stage.log" 2>&1
  sak-lvs.sh -m -w "/work/${band_cell}-lvs" -s /src/pll/vco_band_variants.spice \
    -l "/work/${band_cell}.mag" -c "$band_cell" \
    > "/work/${band_cell}-lvs-stage.log" 2>&1
  sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n "${band_cell}_pex" \
    -w "/work/${band_cell}-pex" "/work/${band_cell}.mag" \
    > "/work/${band_cell}-pex-stage.log" 2>&1
  cp "/work/${band_cell}-drc/${band_cell}.magic.drc/${band_cell}.magic.drc.rpt" \
    "/work/${band_cell}-drc.rpt"
  cp "/work/${band_cell}-lvs/${band_cell}.magic.lvs/${band_cell}.lvs.out" \
    "/work/${band_cell}-lvs.out"
  cp "/work/${band_cell}-pex/${band_cell}.pex.spice" "/work/${band_cell}.pex.spice"
  sed -i '${/^$/d;}' "/work/${band_cell}.pex.spice"
done

python3 /src/pll/compose_vco_band_bank.py --work /work \
  --output /work/layout-vco-band-bank.png
simulation_rc=0
python3 /src/pll/run_vco_band_bank.py --source /src/pll --pex-dir /work \
  --work /work/vco-band-bank-sim --output /work/vco-band-bank-simulation.json \
  || simulation_rc=$?
python3 /src/pll/check_vco_band_bank.py --source /src/pll --work /work \
  --simulation /work/vco-band-bank-simulation.json \
  --render /work/layout-vco-band-bank.png --output /work/vco-band-bank-result.json
exit "$simulation_rc"
