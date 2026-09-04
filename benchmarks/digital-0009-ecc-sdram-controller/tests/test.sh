#!/bin/sh
set -u
mkdir -p /logs/verifier/graded /logs/verifier/gating
rewardkit /tests/graded --workspace /app --output /logs/verifier/graded/reward.json; grc=$?
rewardkit /tests/gating --workspace /app --output /logs/verifier/gating/reward.json; xrc=$?
python3 /tests/finalize.py --graded /logs/verifier/graded/reward.json --graded-rc "$grc" --gating /logs/verifier/gating/reward.json --gating-rc "$xrc" --out /logs/verifier/reward.json
