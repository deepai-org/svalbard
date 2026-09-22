#!/usr/bin/env bash
set -euo pipefail
python3 -B /src/verification/test_rail_checkpoint.py
python3 -B /src/verification/probe_rail_solvers.py
tar -czf /work/rail-solver-artifacts.tar.gz -C /work ideal_sparse ideal_klu both_sparse both_klu
