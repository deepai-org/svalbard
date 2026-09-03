#!/bin/bash
set -uo pipefail

mkdir -p /logs/verifier/graded /logs/verifier/gating
rewardkit /tests/graded --workspace /app --output /logs/verifier/graded/reward.json
graded_rc=$?
rewardkit /tests/gating --workspace /app --output /logs/verifier/gating/reward.json
gating_rc=$?
python3 /tests/finalize.py \
  --graded /logs/verifier/graded/reward.json --graded-rc "$graded_rc" \
  --gating /logs/verifier/gating/reward.json --gating-rc "$gating_rc" \
  --out /logs/verifier/reward.json
