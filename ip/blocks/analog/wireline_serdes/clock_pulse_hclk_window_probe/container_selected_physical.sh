#!/usr/bin/env bash
set -euo pipefail

python3 /src/clock_pulse_hclk_window_probe/test_compile_selected_physical_source.py
python3 /src/clock_pulse_hclk_window_probe/test_selected_pex_contract.py
python3 /src/clock_pulse_hclk_window_probe/compile_selected_physical_source.py \
  --output /work/selected_dual_control_pulse.spice
cmp /work/selected_dual_control_pulse.spice \
  /src/clock_pulse_hclk_window_probe/selected_dual_control_pulse.spice
python3 /src/clock_pulse/generate_pulse_layout.py \
  --source /work/selected_dual_control_pulse.spice \
  --top selected_dual_control_pulse \
  --output /work/selected_dual_control_pulse_layout.tcl
magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /work/selected_dual_control_pulse_layout.tcl > /work/layout.log 2>&1
klayout -b -r /src/clock_pulse_hclk_window_probe/render_selected_layout.py \
  > /work/render.log 2>&1
sak-drc.sh -m -w /work/drc /work/selected_dual_control_pulse.mag \
  > /work/drc-stage.log 2>&1
sak-lvs.sh -m -w /work/lvs \
  -s /work/selected_dual_control_pulse.spice \
  -l /work/selected_dual_control_pulse.mag \
  -c selected_dual_control_pulse > /work/lvs-stage.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n selected_dual_control_pulse_pex \
  -w /work/pex /work/selected_dual_control_pulse.mag \
  > /work/pex-stage.log 2>&1
pex=/work/pex/selected_dual_control_pulse.pex.spice
sed -i -E '1s/^\* PEX produced on .* using /\* PEX produced using /' "$pex"
grep -q '^\* PEX produced using ' "$pex"
cp "$pex" /work/selected_dual_control_pulse.pex.spice
python3 /src/clock_pulse_hclk_window_probe/summarize_selected_physical.py
set +e
python3 /src/clock_pulse_hclk_window_probe/run_selected_pex.py \
  --pex /work/selected_dual_control_pulse.pex.spice \
  --output /work/selected-dual-control-pex.json
pex_result=$?
set -e
exit "$pex_result"
