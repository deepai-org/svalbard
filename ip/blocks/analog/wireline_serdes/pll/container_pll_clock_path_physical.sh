#!/usr/bin/env bash
set -euo pipefail
cd /work

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/startup_assist_layout.tcl > /work/path-assist-layout.log 2>&1
export VCO_SPLIT_CONTROL=1
generate_vco() {
  local suffix="$1"
  export VCO_CELL_NAME="cml_vco_delay_hr_split${suffix}"
  export VCO_BAND_DELAY_CELL="$VCO_CELL_NAME"
  export VCO_BAND_CELL_NAME="cml_vco_band_hr_split${suffix}"
  export VCO_CAP_L="$2" VCO_CAP_W="$3" VCO_LOAD_L="$4"
  export VCO_MAIN_TAIL_W="$5" VCO_LATCH_TAIL_W="$6"
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    /src/pll/layout.tcl > "/work/path${suffix}-delay-layout.log" 2>&1
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
    /src/pll/vco_band_layout.tcl > "/work/path${suffix}-band-layout.log" 2>&1
}
generate_vco _fast 4.48 3.2 4.0 15.0 6.0
generate_vco _gain 3.45 4.0 6.5 10.0 4.0
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/phase_control_dac/layout.tcl > /work/path-dac-layout.log 2>&1
unset VCO_CELL_NAME VCO_BAND_DELAY_CELL VCO_BAND_CELL_NAME
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/selector_unit_layout.tcl > /work/path-selector-layout.log 2>&1
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/vco_bank_top_layout.tcl > /work/path-bank-layout.log 2>&1

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/clock_restorer_layout.tcl > /work/path-restorer-leaf-layout.log 2>&1
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/clock_restorer_cascade_layout.tcl > /work/path-restorer-layout.log 2>&1
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/divider_layout.tcl > /work/path-divider-layout.log 2>&1
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/pll/pll_clock_path_layout.tcl > /work/pll-clock-path-layout.log 2>&1

sak-drc.sh -m -w /work/pll-clock-path-drc /work/pll_clock_path.mag \
  > /work/pll-clock-path-drc-stage.log 2>&1
sak-lvs.sh -m -w /work/pll-clock-path-lvs -s /src/pll/pll_clock_path.spice \
  -l /work/pll_clock_path.mag -c pll_clock_path \
  > /work/pll-clock-path-lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n pll_clock_path_pex \
  -w /work/pll-clock-path-pex /work/pll_clock_path.mag \
  > /work/pll-clock-path-pex-stage.log 2>&1
export VCO_BAND_CELL_NAME=pll_clock_path
export VCO_BAND_RENDER_PATH=/work/layout-pll-clock-path.png
python3 /src/pll/render_vco_band.py > /work/pll-clock-path-render.log 2>&1
drc=/work/pll-clock-path-drc/pll_clock_path.magic.drc/pll_clock_path.magic.drc.rpt
lvs=/work/pll-clock-path-lvs/pll_clock_path.magic.lvs/pll_clock_path.lvs.out
pex=/work/pll-clock-path-pex/pll_clock_path.pex.spice
python3 /src/pll/check_pll_clock_path_physical.py --source /src/pll \
  --drc "$drc" --lvs "$lvs" --pex "$pex" --gds /work/pll_clock_path.gds \
  --render /work/layout-pll-clock-path.png \
  --output /work/pll-clock-path-physical-result.json
cp "$pex" /work/pll-clock-path.pex.spice
