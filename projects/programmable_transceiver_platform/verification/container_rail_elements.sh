#!/usr/bin/env bash
set -euo pipefail
python3 -B /src/verification/test_rail_checkpoint.py
python3 -B /src/verification/probe_rail_elements.py
tar -czf /work/rail-element-artifacts.tar.gz -C /work both_r both_l both_caps both_r_caps
