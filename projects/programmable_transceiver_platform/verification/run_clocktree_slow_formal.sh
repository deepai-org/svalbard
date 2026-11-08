#!/usr/bin/env bash
# Formal proof of rtl/pt_clocktree_slow.sv (P2-10) with SymbiYosys/yices in the pinned
# iic-osic-tools image (the LibreLane canary image has no SMT solver). No network.
# Results: scratch/p2-digital/clocktree_formal/.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../.." && pwd)
PROJ="$ROOT/projects/programmable_transceiver_platform"
OUT="${OUT:-$ROOT/scratch/p2-digital/clocktree_formal}"
RTL="${RTL:-$PROJ/rtl/pt_clocktree_slow.sv}"   # override only for mutation checks
IMAGE="docker.io/hpretl/iic-osic-tools@sha256:89641950bbf247c522188629992b6271e391e38372ca0f8e3c850480874948a3"
rm -rf "$OUT"; mkdir -p "$OUT"
status=0
docker run --rm --network none --cpus 4 --memory 8g --user "$(id -u):$(id -g)" -e HOME=/tmp --entrypoint bash \
  -v "$PROJ:/src:ro" -v "$RTL:/rtl_under_test.sv:ro" -v "$OUT:/out" "$IMAGE" -lc \
  'set -e; cd /out; mkdir -p work rtl; cp /src/verification/formal/pt_clocktree_slow.sby /src/verification/formal/pt_clocktree_slow_fv.sv work/;
   cp /rtl_under_test.sv rtl/pt_clocktree_slow.sv; cd work;
   sed -i "s#../../rtl/pt_clocktree_slow.sv#/out/rtl/pt_clocktree_slow.sv#" pt_clocktree_slow.sby;
   yosys -V; sby -f pt_clocktree_slow.sby' > "$OUT/sby.log" 2>&1 || status=$?
grep -E "DONE|Assert|assert|Reached|cover|failed" "$OUT/sby.log" | tail -20
for t in prove cover; do
  s=$(cat "$OUT/work/pt_clocktree_slow_$t/status" 2>/dev/null || echo missing)
  echo "task $t: $s"
  [[ "$s" == PASS* ]] || exit 1
done
exit $status
