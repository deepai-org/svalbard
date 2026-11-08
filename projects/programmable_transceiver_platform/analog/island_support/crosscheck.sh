#!/bin/sh
# Independent DRC/LVS re-check of the generated GDS in the librelane GF180
# canary image (Magic 8.3.623 / Netgen 1.5.316, PDK at /pdk/gf180mcuD).
# Usage (container): crosscheck.sh CELL ...   reads /work/layout/CELL.{gds,spice}
set -u
PDKD=/pdk/gf180mcuD
mkdir -p /work/xcheck
cd /work/xcheck
echo '{' > /work/crosscheck.json.tmp
first=1
for cell in "$@"; do
  cat > "$cell.tcl" <<EOF
crashbackups stop
gds read /work/layout/$cell.gds
load $cell
select top cell
drc style drc(full)
drc check
drc catchup
set n [drc list count total]
puts "XCHECK_DRC_COUNT \$n"
extract path /work/xcheck
extract all
ext2spice lvs
ext2spice -o /work/xcheck/$cell.ext.spice
quit -noprompt
EOF
  magic -dnull -noconsole -rcfile "$PDKD/libs.tech/magic/gf180mcuD.magicrc" "$cell.tcl" > "$cell.magic.log" 2>&1
  line=$(grep 'XCHECK_DRC_COUNT' "$cell.magic.log" | tail -1)
  drc=${line##* }
  netgen -batch lvs "$cell.ext.spice $cell" "/work/layout/$cell.spice $cell" \
    "$PDKD/libs.tech/netgen/gf180mcuD_setup.tcl" "$cell.lvs.out" > "$cell.netgen.log" 2>&1
  if grep -q "Final result: Circuits match uniquely." "$cell.lvs.out" 2>/dev/null; then lvs=match; else lvs=mismatch; fi
  [ $first -eq 1 ] || echo ',' >> /work/crosscheck.json.tmp
  first=0
  printf '"%s": {"magic_drc_errors": %s, "lvs": "%s"}' "$cell" "${drc:-null}" "$lvs" >> /work/crosscheck.json.tmp
done
printf ', "tools": "%s; %s"}\n' "$(magic --version 2>/dev/null | head -1)" "$(netgen -batch quit 2>&1 | grep -i 'netgen' | head -1)" >> /work/crosscheck.json.tmp
mv /work/crosscheck.json.tmp /work/crosscheck.json
cat /work/crosscheck.json
