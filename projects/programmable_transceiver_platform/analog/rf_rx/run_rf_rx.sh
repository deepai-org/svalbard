#!/usr/bin/env bash
# Reproduce the RF receive family: netlists -> layout/DRC/extraction/LVS -> extracted
# simulations -> generated/<block>-evidence.json.
#
# Host needs python3 + docker.  Every tool runs in a pinned image, offline and bounded
# (--network none --cpus 3 --memory 6g, OMP_NUM_THREADS=1, at most 3 concurrent
# simulations; see rfrx_flow.py):
#   Magic / Netgen : svalbard/librelane-gf180-canary:2026.08
#                    sha256:b60278092f08c0a42fa93ed640d15d84eec53d7799790962781157ec34ceff43
#   ngspice        : hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3
#                    (local image id sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305)
# Raw output: <repo>/scratch/rf_rx/ (gitignored).
#
#   ./run_rf_rx.sh            full run (nominal + 12 corners + chain/LO stretch points, ~1 h)
#   ./run_rf_rx.sh --quick    nominal points only
set -euo pipefail
cd "$(dirname "$0")"
for img in sha256:b60278092f08c0a42fa93ed640d15d84eec53d7799790962781157ec34ceff43 \
           sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305; do
  docker image inspect "$img" >/dev/null || { echo "missing pinned image $img" >&2; exit 2; }
done
python3 netlists.py
for b in lna rxmix_i rxmix_q bbfilter_i bbfilter_q bb_tap; do
  python3 "generate_${b}.py"
done
python3 characterize.py --jobs 3 "$@"
python3 summarize.py
