#!/usr/bin/env bash
set -euo pipefail
python3 /src/clock_pulse_hclk_window_probe/test_recovery_contract.py
python3 /src/clock_pulse_hclk_window_probe/compile_recovery_physical_source.py \
  --revision retimed_joint_long_6_3 \
  --output /work/retimed_recovery_dual_control_pulse.spice
RECOVERY_CONTRACT_PATH=/src/clock_pulse_hclk_window_probe/retimed_recovery_contract.json \
  python3 /src/clock_pulse_hclk_window_probe/run_recovery_schematic.py \
  --source /work/retimed_recovery_dual_control_pulse.spice \
  --work /work/retimed-recovery-cases \
  --output /work/retimed-recovery-schematic-result.json
