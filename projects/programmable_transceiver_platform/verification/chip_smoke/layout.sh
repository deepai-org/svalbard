#!/bin/bash
# Layout netlist for the smoke bench:   layout.sh <rf|wired> <ASM_RUN dir> <work dir> [cut=inst.pin[,inst.pin]]
# Extracts the top level of <run>/chip/pt_chip_top.gds (layout_netlist.py, KLayout, 1 cpu, about 5 min) into
# <work>/layout.spice (+ layout.spice.json). The run dir is only read (mounted read-only); the reference netlist (names, pin
# order) is <run>/lvs/pt_chip_top.ref.spice, else KH_CONN=1 gen_netlist.py of this tree. With cut=..., the metal at those
# instance pins is erased in the in-memory copy of the GDS before extraction (negative control).
set -u
H=$(cd "$(dirname "$0")" && pwd); CHIP=${1:?rf|wired}; RUN=$(cd "${2:?run dir}" && pwd); W=${3:?work dir}; CUT=${4:-}
P=$(cd "$H/../.." && pwd)
mkdir -p "$W"; W=$(cd "$W" && pwd)
[ -s "$RUN/chip/pt_chip_top.gds" ] && [ -s "$RUN/chip/manifest.json" ] || { echo "no chip/pt_chip_top.gds + manifest.json in $RUN"; exit 2; }
cp "$RUN/chip/manifest.json" "$W/manifest.json"
if [ -s "$RUN/lvs/pt_chip_top.ref.spice" ]; then cp "$RUN/lvs/pt_chip_top.ref.spice" "$W/ref.spice"
else KH_CONN=1 python3 "$P/integration/signoff/lvs/gen_netlist.py" "$W/ref.spice" --chip "$CHIP" || exit 2; fi
REL=${H#"$(cd "$P/../.." && pwd)"/}          # this directory relative to the repository root (mounted at /repo)
GR=$(readlink -f "$RUN/chip/pt_chip_top.gds"); GD=$(dirname "$GR")      # the GDS may be a symlink (signoff selftest copies)
SIGNOFF_RUN=$W KL_EXTRA="-v $GD:/src:ro" "$P/integration/signoff/kl.sh" -c 1 "../repo/$REL/layout_netlist.py" \
  -rd gds="../src/$(basename "$GR")" -rd ref=ref.spice -rd manifest=manifest.json -rd out=layout.spice ${CUT:+-rd "$CUT"} > "$W/layout.log" 2>&1
RC=$?; tail -1 "$W/layout.log"
[ $RC -eq 0 ] && [ -s "$W/layout.spice" ]
