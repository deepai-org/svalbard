#!/usr/bin/env bash
set -euo pipefail
python3 /src/clock_pulse_hclk_window_probe/test_compile_selected_physical_source.py
python3 /src/clock_pulse_hclk_window_probe/test_selected_pex_contract.py
python3 /src/clock_pulse_hclk_window_probe/compile_selected_physical_source.py \
  --output /work/selected_dual_control_pulse.spice
python3 /src/clock_pulse_hclk_window_probe/run_selected_pex.py \
  --pex /work/selected_dual_control_pulse.spice \
  --top selected_dual_control_pulse \
  --netlist-kind schematic \
  --output /work/selected-dual-control-schematic-replay.json
