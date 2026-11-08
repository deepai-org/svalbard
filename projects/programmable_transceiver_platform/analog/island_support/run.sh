#!/usr/bin/env bash
# Reproduce the island-support evidence. Host-side wrapper: bounded, offline
# containers; outputs under scratch/; copies evidence.json next to this script.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../../.." && pwd)
PROJ="$ROOT/projects/programmable_transceiver_platform"
IMG=docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3
IMG_ID=sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305
XIMG=svalbard/librelane-gf180-canary:2026.08
CPUS="${CPUS:-12}"; MEM="${MEM:-24g}"
OUT="$ROOT/scratch/island-support-$(date +%Y%m%d-%H%M%S)"
[[ "$(docker image inspect "$IMG" --format '{{.Id}}')" == "$IMG_ID" ]] || { echo "pinned image missing" >&2; exit 2; }
mkdir -p "$OUT"
common=(--rm --platform linux/arm64 --network none --cpus "$CPUS" --memory "$MEM" --memory-swap "$MEM"
        --pids-limit 1024 --cap-drop ALL --security-opt no-new-privileges --user "$(id -u):$(id -g)"
        --env HOME=/tmp --tmpfs /tmp:size=2g,mode=1777)
docker run "${common[@]}" --read-only --env PDK=gf180mcuD --env PDKPATH=/foss/pdks/gf180mcuD \
  --env WORKERS="$CPUS" --env OMP_NUM_THREADS=1 \
  --tmpfs /headless/.data-default:size=16m,mode=0700,uid="$(id -u)",gid="$(id -g)" \
  --mount "type=bind,src=$HERE,dst=/src/analog/island_support,readonly" \
  --mount "type=bind,src=$PROJ/spec/analog-architecture.json,dst=/src/spec/analog-architecture.json,readonly" \
  --mount "type=bind,src=$OUT,dst=/work" --workdir /work \
  --entrypoint /bin/bash "$IMG" -lc 'bash /src/analog/island_support/container_flow.sh'
cells=$(python3 -c "import json;s=json.load(open('$OUT/schematic-result.json'));print(' '.join(['isw_'+i for i in s['sizes']]+['atb_leaf_s','atb_leaf_f','atb_grp','atb_pad','iso_clamp']))")
if docker image inspect "$XIMG" >/dev/null 2>&1; then
  docker run "${common[@]}" --mount "type=bind,src=$HERE,dst=/src,readonly" \
    --mount "type=bind,src=$OUT,dst=/work" --entrypoint /bin/sh "$XIMG" /src/crosscheck.sh $cells > "$OUT/crosscheck.log" 2>&1 || true
  python3 - "$OUT/crosscheck.json" "$(docker image inspect "$XIMG" --format '{{.Id}}')" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p)); d['image'] = 'svalbard/librelane-gf180-canary:2026.08'; d['image_id'] = sys.argv[2]
json.dump(d, open(p, 'w'), indent=1)
PY
fi
python3 "$HERE/summarize.py" --work "$OUT" --out "$OUT/evidence.json"
cp "$OUT/evidence.json" "$HERE/evidence.json"
echo "outputs: $OUT"
