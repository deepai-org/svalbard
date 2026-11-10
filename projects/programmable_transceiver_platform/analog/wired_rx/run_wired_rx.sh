#!/usr/bin/env bash
# Regenerate the wired-receive family (schematics, Magic layout/DRC/extraction,
# Netgen LVS, extracted ngspice nominal + operating-envelope corners, safety
# cases, CDR RTL check, evidence JSON).  Tools run in the pinned images with
# --network none (see wrx_flow.py); raw output goes to scratch/wired_rx/.
set -euo pipefail
cd "$(dirname "$0")"
docker image inspect sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305 >/dev/null
docker image inspect sha256:b60278092f08c0a42fa93ed640d15d84eec53d7799790962781157ec34ceff43 >/dev/null
python3 run_family.py "$@"
# pt_wrx_cap (capture.py): cells, top DRC/LVS/GDS, schematic + extracted benches -> generated/wrx_cap-evidence.json
if [ "$#" -eq 0 ]; then python3 run_capture.py; fi
