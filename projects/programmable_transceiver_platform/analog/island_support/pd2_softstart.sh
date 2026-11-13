#!/usr/bin/env bash
# PD2: rerun the island-switch soft start at the re-partitioned loads on the existing extracted masters.
# Host-side wrapper (pinned image, offline, bounded). Usage: pd2_softstart.sh [EVIDENCE_RUN_DIR]
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../../../.." && pwd); PROJ="$ROOT/projects/programmable_transceiver_platform"
RUN="${1:-$ROOT/scratch/island-support-20261108-075605}"
IMG=docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3
OUT="$ROOT/scratch/island-support-pd2"; mkdir -p "$OUT"
docker run --rm --platform linux/arm64 --network none --cpus "${CPUS:-2}" --memory 8g --pids-limit 512 --cap-drop ALL \
  --security-opt no-new-privileges --user "$(id -u):$(id -g)" --env HOME=/tmp --tmpfs /tmp:size=1g,mode=1777 \
  --env WORKERS="${WORKERS:-2}" --env OMP_NUM_THREADS=1 --env ONLY="${ONLY:-}" \
  --mount "type=bind,src=$HERE,dst=/src/analog/island_support,readonly" \
  --mount "type=bind,src=$PROJ/spec/analog-architecture.json,dst=/src/spec/analog-architecture.json,readonly" \
  --mount "type=bind,src=$RUN,dst=/run,readonly" --mount "type=bind,src=$OUT,dst=/work" --workdir /work \
  --entrypoint /bin/bash "$IMG" -lc 'python3 /src/analog/island_support/pd2_softstart.py /run/pex /run/schematic-result.json /work/pd2-softstart.json'
cp "$OUT/pd2-softstart.json" "$HERE/pd2-softstart.json"
