#!/usr/bin/env bash
set -euo pipefail

make_custom() {
  local cell="$1" wn="$2" wp="$3" schematic="$4"
  NAND_CELL="$cell" NAND_WN="$wn" NAND_WP="$wp" \
    magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
      /src/layout.tcl > "/work/${cell}.layout.log" 2>&1
  sak-drc.sh -m -w "/work/drc-${cell}" "/work/${cell}.mag" > "/work/${cell}.drc.log" 2>&1
  sak-lvs.sh -m -w "/work/lvs-${cell}" -s "$schematic" \
    -l "/work/${cell}.mag" -c "$cell" > "/work/${cell}.lvs.log" 2>&1
  sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n "${cell}_pex" -w "/work/pex-${cell}" \
    "/work/${cell}.mag" > "/work/${cell}.pex.log" 2>&1
}

python3 /src/screen_physical.py > /work/physical-screen.log
make_custom nand2_min_3v3 0.42 0.42 /src/nand2_min.spice
make_custom nand2_fast_3v3 1.05 2.10 /src/nand2_fast.spice

magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" \
  /src/std_layout.tcl > /work/nand2_std_5v.layout.log 2>&1
sak-drc.sh -m -w /work/drc-nand2_std_5v /work/nand2_std_5v.mag > /work/nand2_std_5v.drc.log 2>&1
sak-lvs.sh -m -w /work/lvs-nand2_std_5v -s /src/nand2_std.spice \
  -l /work/nand2_std_5v.mag -c nand2_std_5v > /work/nand2_std_5v.lvs.log 2>&1
sak-pex.sh -m 3 -t 0 -r 1 -y 0 -n nand2_std_5v_pex -w /work/pex-nand2_std_5v \
  /work/nand2_std_5v.mag > /work/nand2_std_5v.pex.log 2>&1

python3 /src/characterize.py \
  --min-pex /work/pex-nand2_min_3v3/nand2_min_3v3.pex.spice \
  --fast-pex /work/pex-nand2_fast_3v3/nand2_fast_3v3.pex.spice \
  --std-pex /work/pex-nand2_std_5v/nand2_std_5v.pex.spice \
  --work /work/characterization --output /work/comparison.json --jobs 4
klayout -b -r /src/render_layout.py > /work/render.log 2>&1
python3 /src/check_results.py --work /work --output /work/result.json
