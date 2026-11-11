#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
PROJ="$ROOT/projects/programmable_transceiver_platform"
OUT="${OUT:-$ROOT/scratch/pair-word-formal/$(date -u +%Y%m%d-%H%M%S)}"
IMAGE="docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3"
mkdir -p "$OUT"
test ! -e "$OUT/source.sha256"
# AC-1: the paired word boundary is replaced by the pad-edge D2H and H2D gearboxes (rtl/pt_host_link.sv);
# both proofs also establish the 1.5-period multicycle exceptions of integration/pt_digital_macro.sdc.
cp "$PROJ/rtl/pt_cells.sv" "$PROJ/rtl/pt_pattern.sv" "$PROJ/rtl/pt_host_link.sv" "$OUT/"
cp "$PROJ/verification/formal/pt_d2h_gearbox.sby" "$PROJ/verification/formal/pt_d2h_gearbox_fv.sv" "$OUT/"
cp "$PROJ/verification/formal/pt_h2d_gearbox.sby" "$PROJ/verification/formal/pt_h2d_gearbox_fv.sv" "$OUT/"
sed -i 's#../../rtl/##' "$OUT/pt_d2h_gearbox.sby" "$OUT/pt_h2d_gearbox.sby"
sha256sum "$OUT"/pt_cells.sv "$OUT"/pt_pattern.sv "$OUT"/pt_host_link.sv "$OUT"/pt_d2h_gearbox.sby "$OUT"/pt_d2h_gearbox_fv.sv "$OUT"/pt_h2d_gearbox.sby "$OUT"/pt_h2d_gearbox_fv.sv > "$OUT/source.sha256"
docker run --rm --network none --cpus 2 --memory 4g --entrypoint bash \
  -v "$OUT:/out" "$IMAGE" -lc \
  'set -e; cd /out; sby -f pt_d2h_gearbox.sby; sby -f pt_h2d_gearbox.sby' > "$OUT/sby.log" 2>&1 || status=$?
tail -n 20 "$OUT/sby.log"
for proof in pt_d2h_gearbox pt_h2d_gearbox; do
  for task in prove cover; do
    read -r result < "$OUT/${proof}_$task/status"
    [[ "$result" == PASS* ]] || exit 1
  done
done
exit "${status:-0}"
