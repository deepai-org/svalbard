#!/usr/bin/env bash
set -euo pipefail
cd /work

# Generate the exact leaf cells selected by the bank-minimization proof.
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/startup_assist_layout.tcl > /work/top-assist-layout.log 2>&1

export VCO_SPLIT_CONTROL=1
generate_vco() {
  local suffix="$1"
  export VCO_CELL_NAME="cml_vco_delay_hr_split${suffix}"
  export VCO_BAND_DELAY_CELL="$VCO_CELL_NAME"
  export VCO_BAND_CELL_NAME="cml_vco_band_hr_split${suffix}"
  export VCO_CAP_L="$2" VCO_CAP_W="$3" VCO_LOAD_L="$4"
  export VCO_MAIN_TAIL_W="$5" VCO_LATCH_TAIL_W="$6"
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    /src/pll/layout.tcl > "/work/top${suffix}-delay-layout.log" 2>&1
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    /src/pll/vco_band_layout.tcl > "/work/top${suffix}-band-layout.log" 2>&1
}
generate_vco _fast 4.48 3.2 4.0 15.0 6.0
generate_vco _gain 3.45 4.0 6.5 10.0 4.0

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/phase_control_dac/layout.tcl > /work/top-dac-layout.log 2>&1
unset VCO_CELL_NAME VCO_BAND_DELAY_CELL VCO_BAND_CELL_NAME
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/selector_unit_layout.tcl > /work/top-selector-layout.log 2>&1
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/vco_bank_top_layout.tcl > /work/vco-bank-top-layout.log 2>&1

sak-drc.sh -m -w /work/vco-bank-top-drc /work/vco_bank_top.mag \
  > /work/vco-bank-top-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/vco-bank-top-lvs \
  -s /src/pll/vco_bank_top.spice -l /work/vco_bank_top.mag -c vco_bank_top \
  > /work/vco-bank-top-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n vco_bank_top_pex \
  -w /work/vco-bank-top-pex /work/vco_bank_top.mag \
  > /work/vco-bank-top-pex-stage.log 2>&1

export VCO_BAND_CELL_NAME=vco_bank_top
export VCO_BAND_RENDER_PATH=/work/layout-vco-bank-top.png
python3 /src/pll/render_vco_band.py > /work/vco-bank-top-render.log 2>&1

drc=/work/vco-bank-top-drc/vco_bank_top.magic.drc/vco_bank_top.magic.drc.rpt
lvs=/work/vco-bank-top-lvs/vco_bank_top.magic.lvs/vco_bank_top.lvs.out
pex=/work/vco-bank-top-pex/vco_bank_top.pex.spice
python3 /src/pll/check_vco_bank_top.py --source /src/pll \
  --drc "$drc" --lvs "$lvs" --pex "$pex" --gds /work/vco_bank_top.gds \
  --render /work/layout-vco-bank-top.png \
  --output /work/vco-bank-top-physical-result.json
python3 /src/pll/run_vco_bank_top_nominal.py --source /src/pll --pex "$pex" \
  --work /work/vco-bank-top-nominal-sim \
  --output /work/vco-bank-top-nominal-result.json
python3 /src/pll/run_vco_bank_top_pvt.py --source /src/pll --pex "$pex" \
  --work /work/vco-bank-top-pvt-sim \
  --output /work/vco-bank-top-pvt-result.json
python3 /src/pll/run_vco_bank_top_supply.py --source /src/pll --pex "$pex" \
  --pvt /work/vco-bank-top-pvt-result.json \
  --work /work/vco-bank-top-supply-sim \
  --output /work/vco-bank-top-supply-result.json
python3 /src/pll/run_vco_bank_top_sequence.py --source /src/pll --pex "$pex" \
  --work /work/vco-bank-top-sequence-sim \
  --output /work/vco-bank-top-sequence-result.json
python3 /src/pll/check_vco_bank_top_result.py \
  --physical /work/vco-bank-top-physical-result.json \
  --bias-dac /src/pll/vco_bias_dac_result.json \
  --nominal /work/vco-bank-top-nominal-result.json \
  --pvt /work/vco-bank-top-pvt-result.json \
  --supply /work/vco-bank-top-supply-result.json \
  --sequence /work/vco-bank-top-sequence-result.json \
  --output /work/vco-bank-top-result.json
cp "$pex" /work/vco-bank-top.pex.spice
