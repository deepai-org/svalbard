#!/usr/bin/env bash
# Regenerate the whole rf_tx family: netlists, layouts (Magic), DRC, extraction, LVS (Netgen),
# schematic and extracted ngspice benches, and per-block evidence records.
# Tools run in the pinned images with --network none (see layoutlib.py / simulate.py):
#   digital  svalbard/librelane-gf180-canary:2026.08  (Magic 8.3.623, Netgen 1.5.316, /pdk/gf180mcuD)
#   analog   hpretl/iic-osic-tools@sha256:89641950...  (ngspice, Magic 8.3.678 GDS export, KLayout DRC; /foss/pdks/gf180mcuD)
# Raw work goes to <repo>/scratch/rf_tx/; compact outputs to ./generated/.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
cd "$HERE"
python3 circuits.py
for b in txmix_i txmix_q txsum rfdriver; do
  python3 "generate_$b.py"
done
# GDS export with the analog image's Magic 8.3.678 (HRES marker rule) + KLayout GF180 DRC on that GDS
python3 gds_export.py txmix_i txmix_q txsum rfdriver
python3 run_benches.py --view sch > /dev/null
python3 run_benches.py --view ext > /dev/null
python3 evidence.py
