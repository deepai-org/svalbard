#!/usr/bin/env bash
set -euo pipefail
python3 /src/clock_pulse_hclk_window_probe/test_recovery_contract.py
python3 /src/clock_pulse_hclk_window_probe/compile_recovery_physical_source.py \
  --revision retimed_joint_long_6_3_compact \
  --output /work/retimed_compact_recovery.spice
compact_rc=0
RECOVERY_CONTRACT_PATH=/src/clock_pulse_hclk_window_probe/retimed_recovery_contract.json \
  python3 /src/clock_pulse_hclk_window_probe/run_recovery_schematic.py \
  --source /work/retimed_compact_recovery.spice \
  --work /work/retimed-compact-cases \
  --output /work/retimed-compact-result.json || compact_rc=$?
if [[ "$compact_rc" -ne 0 && "$compact_rc" -ne 1 ]]; then
  exit "$compact_rc"
fi
