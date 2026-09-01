#!/usr/bin/env bash
set -euo pipefail
python3 /src/clock_pulse_hclk_window_probe/test_recovery_contract.py
python3 /src/clock_pulse_hclk_window_probe/compile_recovery_physical_source.py \
  --revision retimed_joint_long_6_3_latched_strong \
  --output /work/retimed_latched_recovery.spice
latched_rc=0
RECOVERY_CONTRACT_PATH=/src/clock_pulse_hclk_window_probe/retimed_recovery_contract.json \
  python3 /src/clock_pulse_hclk_window_probe/run_recovery_schematic.py \
  --source /work/retimed_latched_recovery.spice \
  --work /work/retimed-latched-cases \
  --output /work/retimed-latched-result.json || latched_rc=$?
if [[ "$latched_rc" -ne 0 && "$latched_rc" -ne 1 ]]; then
  exit "$latched_rc"
fi
