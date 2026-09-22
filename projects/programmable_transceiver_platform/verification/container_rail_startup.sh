#!/usr/bin/env bash
set -euo pipefail
python3 -B /src/verification/probe_rail_startup.py
tar -czf /work/rail-startup-artifacts.tar.gz -C /work ideal supply_only return_only both
