#!/usr/bin/env bash
set -euo pipefail

run_physical() {
  local cell="$1"
  local schematic="$2"
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    /src/layout.tcl > "/work/${cell}-layout.log" 2>&1
  sak-drc.sh -m -w "/work/${cell}-drc" "/work/${cell}.mag" \
    > "/work/${cell}-drc-stage.log" 2>&1
  sak-lvs.sh -m -w "/work/${cell}-lvs" -s "$schematic" \
    -l "/work/${cell}.mag" -c "$cell" > "/work/${cell}-lvs-stage.log" 2>&1
  sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n "${cell}_pex" \
    -w "/work/${cell}-pex" "/work/${cell}.mag" \
    > "/work/${cell}-pex-stage.log" 2>&1
  cp "/work/${cell}-drc/${cell}.magic.drc/${cell}.magic.drc.rpt" \
    "/work/${cell}-drc.rpt"
  cp "/work/${cell}-lvs/${cell}.magic.lvs/${cell}.lvs.out" \
    "/work/${cell}-lvs.out"
  cp "/work/${cell}-pex/${cell}.pex.spice" "/work/${cell}.pex.spice"
}

# Regenerate and independently close the startup assist.
export VCO_CELL_NAME=cml_vco_startup_assist
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/startup_assist_layout.tcl > /work/startup-assist-layout.log 2>&1
klayout -b -r /src/render_layout.py > /work/startup-assist-render.log 2>&1
sak-drc.sh -m -w /work/startup-assist-drc /work/cml_vco_startup_assist.mag \
  > /work/startup-assist-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/startup-assist-lvs -s /src/startup_assist.spice \
  -l /work/cml_vco_startup_assist.mag -c cml_vco_startup_assist \
  > /work/startup-assist-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n cml_vco_startup_assist_pex \
  -w /work/startup-assist-pex /work/cml_vco_startup_assist.mag \
  > /work/startup-assist-pex-stage.log 2>&1
cp /work/startup-assist-drc/cml_vco_startup_assist.magic.drc/cml_vco_startup_assist.magic.drc.rpt \
  /work/startup-assist-drc.rpt
cp /work/startup-assist-lvs/cml_vco_startup_assist.magic.lvs/cml_vco_startup_assist.lvs.out \
  /work/startup-assist-lvs.out
cp /work/startup-assist-pex/cml_vco_startup_assist.pex.spice \
  /work/startup-assist.pex.spice

# Regenerate only the seven delay tiles used by the startup proof.
variants=(center slow fast ss_ff_margin_slow ss_ff_margin_fast margin_slow margin_fast)
cap_lengths=(0.8 2.4 0.6 0.40 0.37 0.50 0.37)
cap_widths=(4.0 4.0 4.0 4.0 3.2 4.0 3.2)
load_lengths=(5.25 5.25 5.25 6.25 6.25 4.00 4.00)
main_tail_widths=(10.0 10.0 10.0 15.0 15.0 15.0 15.0)
latch_tail_widths=(4.0 4.0 4.0 5.0 5.0 6.0 6.0)

for index in "${!variants[@]}"; do
  variant="${variants[$index]}"
  if [[ "$variant" == center ]]; then
    cell=cml_vco_delay
    schematic=/src/ring_vco.spice
  else
    cell="cml_vco_delay_${variant}"
    schematic=/src/physical_variants.spice
  fi
  export VCO_CELL_NAME="$cell"
  export VCO_CAP_L="${cap_lengths[$index]}"
  export VCO_CAP_W="${cap_widths[$index]}"
  export VCO_LOAD_L="${load_lengths[$index]}"
  export VCO_MAIN_TAIL_W="${main_tail_widths[$index]}"
  export VCO_LATCH_TAIL_W="${latch_tail_widths[$index]}"
  run_physical "$cell" "$schematic"
done

python3 /src/run_startup_composed.py --source /src --pex-dir /work \
  --assist-pex /work/startup-assist.pex.spice --work /work/startup-sim \
  --output /work/startup-simulation-result.json
python3 /src/check_startup_composed.py --source /src --work /work \
  --simulation /work/startup-simulation-result.json \
  --output /work/startup-composed-result.json
