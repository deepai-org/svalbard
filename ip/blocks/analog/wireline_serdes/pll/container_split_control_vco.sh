#!/usr/bin/env bash
set -euo pipefail
cd /work

export VCO_SPLIT_CONTROL=1
environment_set="${SPLIT_ENVIRONMENT_SET:-focused}"
if [[ "$environment_set" != "focused" && "$environment_set" != "full" ]]; then
  printf 'invalid SPLIT_ENVIRONMENT_SET: %s\n' "$environment_set" >&2
  exit 2
fi
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/startup_assist_layout.tcl > /work/split-assist-layout.log 2>&1

run_variant() {
  local suffix="$1"
  export VCO_CELL_NAME="cml_vco_delay_hr_split${suffix}"
  export VCO_BAND_DELAY_CELL="$VCO_CELL_NAME"
  export VCO_BAND_CELL_NAME="cml_vco_band_hr_split${suffix}"
  export VCO_CAP_L="$2"
  export VCO_CAP_W="$3"
  export VCO_LOAD_L="$4"
  export VCO_MAIN_TAIL_W="$5"
  export VCO_LATCH_TAIL_W="$6"
  local tag="split${suffix:-_base}"
  local report_suffix="screen"
  if [[ "$environment_set" == "full" ]]; then
    report_suffix="full-screen"
  fi
  export VCO_BAND_RENDER_PATH="/work/layout-${tag}-control-vco.png"

  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    /src/pll/layout.tcl > "/work/${tag}-delay-layout.log" 2>&1
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    /src/pll/vco_band_layout.tcl > "/work/${tag}-band-layout.log" 2>&1
  python3 /src/pll/render_vco_band.py > "/work/${tag}-band-render.log" 2>&1

  sak-drc.sh -m -w "/work/${tag}-band-drc" "/work/${VCO_BAND_CELL_NAME}.mag" \
    > "/work/${tag}-band-drc-stage.log" 2>&1
  sak-lvs.sh -m -w "/work/${tag}-band-lvs" \
    -s /src/pll/split_control_vco.spice \
    -l "/work/${VCO_BAND_CELL_NAME}.mag" -c "$VCO_BAND_CELL_NAME" \
    > "/work/${tag}-band-lvs-stage.log" 2>&1
  sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n "${VCO_BAND_CELL_NAME}_pex" \
    -w "/work/${tag}-band-pex" "/work/${VCO_BAND_CELL_NAME}.mag" \
    > "/work/${tag}-band-pex-stage.log" 2>&1

  cp "/work/${tag}-band-drc/${VCO_BAND_CELL_NAME}.magic.drc/${VCO_BAND_CELL_NAME}.magic.drc.rpt" \
    "/work/${tag}-control-vco-drc.rpt"
  cp "/work/${tag}-band-lvs/${VCO_BAND_CELL_NAME}.magic.lvs/${VCO_BAND_CELL_NAME}.lvs.out" \
    "/work/${tag}-control-vco-lvs.out"
  cp "/work/${tag}-band-pex/${VCO_BAND_CELL_NAME}.pex.spice" \
    "/work/${tag}-control-vco.pex.spice"
  sed -i '${/^$/d;}' "/work/${tag}-control-vco.pex.spice"

  python3 /src/pll/screen_split_control_vco.py --source /src/pll \
    --work "/work/${tag}-control-sim" \
    --pex "/work/${tag}-control-vco.pex.spice" \
    --pex-subckt "${VCO_BAND_CELL_NAME}_pex" \
    --claim "physical_${tag}_tail_control_vco_margin_screen" \
    --environment-set "$environment_set" \
    --drc "/work/${tag}-control-vco-drc.rpt" \
    --lvs "/work/${tag}-control-vco-lvs.out" \
    --render "$VCO_BAND_RENDER_PATH" \
    --output "/work/${tag}-control-vco-${report_suffix}.json"
}

# Slow-device/slow-resistor and slow-device/fast-resistor coarse topologies.
run_variant "" 4.75 3.2 4.0 15.0 6.0
run_variant "_fast" 4.48 3.2 4.0 15.0 6.0
run_variant "_gain" 3.45 4.0 6.5 10.0 4.0

if [[ "$environment_set" == "focused" ]]; then
  python3 /src/pll/combine_split_control_vco.py \
    --inputs /work/split_base-control-vco-screen.json \
      /work/split_fast-control-vco-screen.json \
      /work/split_gain-control-vco-screen.json \
    --output /work/split-control-bank-screen.json
else
  python3 /src/pll/combine_split_control_vco.py \
    --scope full --minimize-members \
    --inputs /work/split_base-control-vco-full-screen.json \
      /work/split_fast-control-vco-full-screen.json \
      /work/split_gain-control-vco-full-screen.json \
    --output /work/split-control-full-bank-result.json
  python3 /src/pll/combine_half_rate_vco_full_bank.py \
    --baseline /src/pll/half_rate_vco_bank_result.json \
    --split-inputs /work/split_base-control-vco-full-screen.json \
      /work/split_fast-control-vco-full-screen.json \
      /work/split_gain-control-vco-full-screen.json \
    --output /work/half-rate-vco-full-bank-result.json
fi
