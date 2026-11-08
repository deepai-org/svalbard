#!/bin/sh
# Cross-check of Magic DRC + Magic/Netgen LVS with the digital (librelane canary)
# image, i.e. a second Magic/Netgen/PDK build (magic 8.3.623, netgen 1.5.316).
# Uses the block copies and regenerated schematic netlists left in /work/clean
# by clean_flow.sh (analog image).  POSIX sh: the canary image has no bash.
PDK_ROOT=${PDK_ROOT:-/pdk}; PDK=gf180mcuD; export PDK_ROOT PDK PDKPATH=$PDK_ROOT/$PDK
SCLIB=gf180mcu_as_sc_mcu7t3v3
for blk in ${BLOCKS:-por biasgen biasgen_patched bandgap bandgap_patched}; do
  base=${blk%_patched}; cell=gf180mcu_ocd_ip__$base
  in=/work/clean/$blk; out=/work/canary/$blk
  rm -rf "$out"; mkdir -p "$out/ext"
  cat > "$out/run.tcl" <<EOS
crashbackups stop
addpath $in/src/magic
addpath $in/src/magic/paramcells
load $cell
select top cell
drc euclidean on
drc style drc(full)
drc check
drc catchup
set fh [open $out/magic_drc.txt w]
puts \$fh "style: [drc list style]"
puts \$fh "total: [drc list count total]"
close \$fh
extract path $out/ext
extract do unique
extract no all
extract all
ext2spice lvs
ext2spice -p $out/ext -o $out/layout_lvs.spice
quit -noprompt
EOS
  magic -dnull -noconsole -rcfile $PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc "$out/run.tcl" > "$out/magic.log" 2>&1 < /dev/null
  sch=$(cat $in/lvs_schematic_source.txt)
  lay=$out/layout_lvs.spice; res=$out/lvs_comp.out
  if [ "$base" = biasgen ]; then
    python3 /src/flow/tie_nets.py "$sch" "$out/sch_tiedgnd.spice" $cell dvss avss
    python3 /src/flow/tie_nets.py "$lay" "$out/layout_tiedgnd.spice" $cell dvss avss
  fi
  for v in plain tiedgnd; do
    if [ $v = tiedgnd ]; then [ "$base" = biasgen ] || continue; s=$out/sch_tiedgnd.spice; l=$out/layout_tiedgnd.spice; r=$out/lvs_comp_tiedgnd.out
    else s=$sch; l=$lay; r=$res; fi
    cat > "$out/netgen_$v.tcl" <<EOS
set circuit1 [readnet spice $l]
set circuit2 [readnet spice $PDK_ROOT/$PDK/libs.ref/$SCLIB/spice/$SCLIB.spice]
readnet spice $s \$circuit2
lvs "\$circuit1 $cell" "\$circuit2 $cell" $PDK_ROOT/$PDK/libs.tech/netgen/${PDK}_setup.tcl $r
EOS
    NETGEN_COLUMNS=75 netgen -batch source "$out/netgen_$v.tcl" > "$out/netgen_$v.log" 2>&1 < /dev/null
  done
  # Negative control for the HRES check: a GDS exported by this image's Magic
  # (the export the GDS rule forbids).  run_core_support.sh checks it in the analog image.
  printf 'crashbackups stop\ndrc off\naddpath %s/src/magic\naddpath %s/src/magic/paramcells\nload %s\ngds write %s/canary_export.gds\nquit -noprompt\n' \
    "$in" "$in" "$cell" "$out" > "$out/export.tcl"
  magic -dnull -noconsole -rcfile $PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc "$out/export.tcl" > "$out/export.log" 2>&1 < /dev/null
  magic --version > "$out/tool_versions.txt" 2>&1; netgen -batch quit 2>&1 | head -3 >> "$out/tool_versions.txt"
  echo "$blk canary cross-check done"
done
