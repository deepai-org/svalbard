#!/usr/bin/env bash
# Container-side: generate layout for the listed cells, run Magic DRC, KLayout
# DRC (macro deck), Netgen LVS and Magic PEX. Usage: physical.sh CELL:KIND:NF ...
set -uo pipefail
SRC=/src/analog/island_support
mkdir -p /work/layout /work/drc /work/lvs /work/pex
cd /work/layout
python3 - "$@" <<'PY'
import json, sys
sys.path.insert(0, '/src/analog/island_support')
import layout
cells = []
for arg in sys.argv[1:]:
    name, kind, nf = arg.split(':')
    cells.append((name, kind, int(nf) if nf != '-' else None))
info = layout.generate('/work/layout', cells)
json.dump(info, open('/work/layout/layout-info.json', 'w'), indent=1)
PY
for spec in "$@"; do
  cell="${spec%%:*}"
  magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" "/work/layout/$cell.tcl" \
    > "/work/layout/$cell.magic.log" 2>&1
  test -s "/work/layout/$cell.mag" || { echo "LAYOUT_FAIL $cell"; continue; }
  sak-drc.sh -m -w "/work/drc/$cell" "/work/layout/$cell.mag" > "/work/drc/$cell.stage.log" 2>&1
  echo "DRC_MAGIC_RC $cell $?"
  sak-drc.sh -k -w "/work/drc/$cell-klayout" "/work/layout/$cell.gds" > "/work/drc/$cell-klayout.stage.log" 2>&1
  echo "DRC_KLAYOUT_RC $cell $?"
  sak-lvs.sh -m -w "/work/lvs/$cell" -s "/work/layout/$cell.spice" -l "/work/layout/$cell.mag" -c "$cell" \
    > "/work/lvs/$cell.stage.log" 2>&1
  echo "LVS_RC $cell $?"
  sak-pex.sh -m 2 -n "${cell}_pex" -w "/work/pex/$cell" "/work/layout/$cell.mag" > "/work/pex/$cell.stage.log" 2>&1
  echo "PEX_RC $cell $?"
  case "$cell" in isw_*) ;; *)
    # Default-mode ext2spice C-coupled extraction. sak-pex runs ext2spice in
    # 'lvs' mode, which was found to move the substrate capacitance of
    # gate-only nets (SEL, SWB) onto the switch nodes (NODE, MID).
    mkdir -p "/work/pexd/$cell"
    printf 'crashbackups stop\ndrc off\nload /work/layout/%s\nselect top cell\nflatten %s_flat\nload %s_flat\nextract all\next2spice format ngspice\next2spice scale off\next2spice subcircuit top on\next2spice cthresh 0.01\next2spice -o /work/pexd/%s/%s.pex.spice\nquit -noprompt\n' \
      "$cell" "$cell" "$cell" "$cell" "$cell" > "/work/pexd/$cell/x.tcl"
    (cd "/work/pexd/$cell" && magic -dnull -noconsole -rcfile "$PDKPATH/libs.tech/magic/$PDK.magicrc" x.tcl > x.log 2>&1)
    test -s "/work/pexd/$cell/$cell.pex.spice"; echo "PEXD_RC $cell $?" ;;
  esac
done
exit 0
