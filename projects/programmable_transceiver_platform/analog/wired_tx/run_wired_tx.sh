#!/usr/bin/env bash
# Reproduce every wired-TX deliverable (netlist, layout, DRC/LVS, extraction,
# simulations, evidence).  Tools run in the pinned images with --network none:
#   digital image (svalbard/librelane-gf180-canary:2026.08): Magic layout/DRC/extraction, Netgen LVS
#   analog image  (hpretl/iic-osic-tools@sha256:8964...):    GDS export (Magic 8.3.678), KLayout DRC, ngspice 43
# Pad-integration decks use the pads family's recorded patched ngspice-47 host
# binary (scratch/pad-ngspice47, see analog/pads/generated/simulator-build.json).
# Raw output goes to scratch/wired_tx/ (gitignored).
#   ./run_wired_tx.sh            all stages
#   ./run_wired_tx.sh layout     only netlist + layout + DRC/LVS
#   ./run_wired_tx.sh sims [job...]  simulations (all, or the named jobs)
#   ./run_wired_tx.sh evidence   rebuild generated/*-evidence.json
set -euo pipefail
cd "$(dirname "$0")"
stage="${1:-all}"; shift || true
if [ "$stage" = sims ] && [ "$#" -gt 0 ]; then
  exec python3 run_all.py --stage sims --only "$@"
fi
exec python3 run_all.py --stage "$stage"
