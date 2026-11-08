#!/usr/bin/env bash
# Formal proof of the generated register file with SymbiYosys/yices in the pinned
# iic-osic-tools image (no network). Results: scratch/pt_regfile/formal/.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
PROJ="$ROOT/projects/programmable_transceiver_platform"
OUT="${OUT:-$ROOT/scratch/pt_regfile/formal}"
RTL="${RTL:-$PROJ/rtl/pt_regfile.sv}"   # override only for mutation checks
# SVALBARD_DIGITAL_IMAGE is deliberately not used: the LibreLane canary image has no SMT solver
# (no yices/boolector/bitwuzla/z3), so sby must run in the iic-osic-tools image.
IMAGE="docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3"
rm -rf "$OUT"; mkdir -p "$OUT"
docker run --rm --network none --cpus 4 --memory 8g --entrypoint bash \
  -v "$PROJ:/src:ro" -v "$RTL:/rtl_under_test.sv:ro" -v "$OUT:/out" "$IMAGE" -lc \
  'set -e; cd /out; cp -r /src/verification/formal work; mkdir -p rtl; cp /rtl_under_test.sv rtl/pt_regfile.sv;
   cd work; sed -i "s#../../rtl/pt_regfile.sv#/out/rtl/pt_regfile.sv#" pt_regfile.sby;
   yosys -V; sby -V 2>/dev/null || true; sby -f pt_regfile.sby' > "$OUT/sby.log" 2>&1 || status=$?
grep -E "DONE|summary|PASS|FAIL|Assert|assert|Reached|cover" "$OUT/sby.log" | tail -40
for t in prove cover; do
  s=$(cat "$OUT/work/pt_regfile_$t/status" 2>/dev/null || echo missing)
  echo "task $t: $s"
  [[ "$s" == PASS* ]] || exit 1
done
exit ${status:-0}
