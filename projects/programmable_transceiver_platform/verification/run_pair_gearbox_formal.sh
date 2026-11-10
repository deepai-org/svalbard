#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
PROJ="$ROOT/projects/programmable_transceiver_platform"
OUT="${OUT:-$ROOT/scratch/pair-gearbox-formal/$(date -u +%Y%m%d-%H%M%S)}"
IMAGE="docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3"
mkdir -p "$OUT"
test ! -e "$OUT/source.sha256"
cp "$PROJ/rtl/pt_pair_gearbox.sv" "$OUT/"
cp "$PROJ/verification/formal/pt_pair_gearbox.sby" "$OUT/"
sed -i 's#../../rtl/pt_pair_gearbox.sv#pt_pair_gearbox.sv#' "$OUT/pt_pair_gearbox.sby"
sha256sum "$OUT/pt_pair_gearbox.sv" "$OUT/pt_pair_gearbox.sby" > "$OUT/source.sha256"
docker run --rm --network none --cpus 2 --memory 4g --entrypoint bash \
  -v "$OUT:/out" "$IMAGE" -lc 'set -e; cd /out; sby -f pt_pair_gearbox.sby' \
  > "$OUT/sby.log" 2>&1 || status=$?
tail -n 12 "$OUT/sby.log"
for task in pack unpack; do
  read -r result < "$OUT/pt_pair_gearbox_${task}/status"
  [[ "$result" == PASS* ]]
done
exit "${status:-0}"
