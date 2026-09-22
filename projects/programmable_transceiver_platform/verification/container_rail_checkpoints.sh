#!/usr/bin/env bash
set -euo pipefail
python3 -B /src/verification/probe_rail_checkpoints.py
tar -czf /work/rail-checkpoint-artifacts.tar.gz -C /work ideal supply_only return_only both
