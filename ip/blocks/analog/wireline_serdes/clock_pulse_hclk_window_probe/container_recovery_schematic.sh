#!/usr/bin/env bash
set -euo pipefail
python3 /src/clock_pulse_hclk_window_probe/test_recovery_contract.py
python3 /src/clock_pulse_hclk_window_probe/compile_recovery_physical_source.py \
  --output /work/recovery_dual_control_pulse.spice
python3 /src/clock_pulse_hclk_window_probe/run_recovery_schematic.py \
  --source /work/recovery_dual_control_pulse.spice \
  --work /work/recovery-cases \
  --output /work/recovery-schematic-result.json
