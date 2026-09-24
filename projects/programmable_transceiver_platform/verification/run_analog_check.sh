#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
output_name=${1:?output directory name required}
runner_name=${2:?relative Python checker path required}
[[ "$output_name" =~ ^[a-z0-9-]+$ && "$runner_name" =~ ^[a-zA-Z0-9_]+(/[a-zA-Z0-9_]+)*\.py$ ]] || exit 2
OUT="$ROOT/scratch/$output_name"
case "${4:-reuse}" in
 reuse) mkdir -p "$OUT" ;;
 fresh) mkdir "$OUT" ;;
 *) exit 2 ;;
esac
extra_mounts=()
case "${3:-basic}" in
 basic) ;;
 rf_references)
  extra_mounts=(-v "$ROOT/ip/blocks/analog/wireline_serdes/pll:/vco:ro"
                -v "$ROOT/ip/blocks/analog/wifi_80211b:/wifi:ro"
                -v "$ROOT/scratch/transceiver-rf-ac-clock:/clock:ro"
                -v "$ROOT/scratch/transceiver-rf-ideal-lo:/reference:ro") ;;
 *) exit 2 ;;
esac
docker run --rm --platform linux/arm64 --network none --cpus 2 --memory 4g --entrypoint /bin/bash \
 -v "$ROOT/projects/programmable_transceiver_platform/analog:/screen:ro" \
 "${extra_mounts[@]}" \
 -v "$OUT:/work" --workdir /work \
 sha256:bd7a702bef0b85f5ebf67efca449f270fbeb185380ead204559fcd2457959305 \
 -lc "python3 /screen/$runner_name"
