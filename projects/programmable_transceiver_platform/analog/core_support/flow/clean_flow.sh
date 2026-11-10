#!/bin/bash
# Container-side "clean" flow for the vendored POR and biasgen cells.
# Runs inside the pinned iic-osic-tools image with:
#   /src  = analog/core_support (read-only)
#   /work = scratch work directory
#   $PDK_ROOT/$PDK/libs.ref/gf180mcu_as_sc_mcu7t3v3 = pinned Avalon 3.3 V std-cell library
# Per block: xschem netlist regeneration, Magic DRC (drc(full)), Magic LVS
# extraction, Netgen LVS, Magic parasitic extraction (R+C, C-only fallback),
# KLayout DRC of the vendored GDS.
set -u
export PDK_ROOT=${PDK_ROOT:-/foss/pdks} PDK=${PDK:-gf180mcuD}
export PDKPATH=$PDK_ROOT/$PDK
SCLIB=gf180mcu_as_sc_mcu7t3v3
BLOCKS=${BLOCKS:-"por biasgen biasgen_patched bandgap bandgap_patched"}
KLAYOUT_DRC=${KLAYOUT_DRC:-1}
MAGICRC=$PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc

# Upstream schematics reference PDK symbols both as symbols/<dev>.sym and as
# gf180mcu_fd_pr/<dev>.sym; alias the second form to the same PDK directory.
mkdir -p /tmp/xsym && ln -sfn $PDK_ROOT/$PDK/libs.tech/xschem/symbols /tmp/xsym/gf180mcu_fd_pr

pex_script() { # $1 = out dir, $2 = cell, $3 = resistance|none
  cat <<EOS
crashbackups stop
drc off
addpath $1/src/magic
addpath $1/src/magic/paramcells
load $2
select top cell
extract path $1/ext_pex
extract do capacitance
extract do coupling
extract do adjust
EOS
  if [ "$3" = resistance ]; then
    printf 'extract do resistance\nextract all\nextresist tolerance 10\nextresist all\n'
  else
    printf 'extract no resistance\nextract all\n'
  fi
  cat <<EOS
ext2spice lvs
ext2spice hierarchy off
ext2spice format ngspice
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice extresist $([ "$3" = resistance ] && echo on || echo off)
ext2spice subcircuit top on
ext2spice -p $1/ext_pex -o $1/layout_pex.spice
quit -noprompt
EOS
}

for blk in $BLOCKS; do
  base=${blk%_patched}
  cell=gf180mcu_ocd_ip__$base
  out=/work/clean/$blk
  rm -rf "$out"; mkdir -p "$out"
  cp -r /src/$base/. "$out/src"
  chmod -R u+w "$out/src"
  cd "$out"
  if [ "$blk" != "$base" ]; then
    # Local candidate fix (not upstream): apply every patch for this block.
    for p in /src/patches/$base-*.patch; do
      [ -e "$p" ] || continue   # a *_patched block may have no patches (export-only)
      ( cd src && patch -p1 --no-backup-if-mismatch < "$p" ) > patch.log 2>&1 || { echo "patch failed: $p"; continue 2; }
    done
  fi

  # 1. Regenerate the schematic netlist from the vendored xschem sources.
  printf 'source [file dirname [info script]]/xschemrc\nappend XSCHEM_LIBRARY_PATH :/tmp/xsym\n' \
    > src/xschem/xschemrc_svalbard
  ( cd src/xschem && xschem -n -s -r -x -q --tcl "set top_is_subckt 1" --rcfile ./xschemrc_svalbard \
      -o "$out" -N sch.spice $cell.sch ) > xschem.log 2>&1
  norm() { grep -v -e '^\*\* sch_path' -e '^\*\* sym_path' "$1" | sed -e 's/ par=[0-9]*$//' -e 's/ m=1$//'; }
  if [ -s sch.spice ] && ! grep -q 'IS MISSING' sch.spice; then
    if diff <(norm sch.spice) <(norm src/netlist/schematic/$cell.spice) > sch_vs_vendored.diff; then
      echo identical_after_normalization > sch_vs_vendored.txt
    else
      echo different > sch_vs_vendored.txt
    fi
    schnet=$out/sch.spice
  else
    echo xschem_failed > sch_vs_vendored.txt
    schnet=$out/src/netlist/schematic/$cell.spice
  fi
  echo "$schnet" > lvs_schematic_source.txt

  if [ "$blk" != "$base" ]; then
    # Tapeout views of the patched cell, generated as upstream does
    # (magic/run_gen_gds_lef_*.sh): standard cells from the Avalon GDS, then
    # GDS and LEF of the patched Magic view.  DRC/LVS below run on this GDS.
    mkdir -p tapeout
    cat > magic_tapeout.tcl <<EOS
crashbackups stop
drc off
gds read $PDK_ROOT/$PDK/libs.ref/$SCLIB/gds/$SCLIB.gds
addpath $out/src/magic
addpath $out/src/magic/paramcells
load $cell
select top cell
expand
select top cell
cif ostyle gdsii
gds compress 9
gds write $out/tapeout/$cell
select top cell
lef write $out/tapeout/$cell.lef -hide
quit -noprompt
EOS
    ( cd tapeout && magic -dnull -noconsole -rcfile $MAGICRC ../magic_tapeout.tcl > ../magic_tapeout.log 2>&1 < /dev/null )
    gds_in=$out/tapeout/$cell.gds.gz
  else
    gds_in=$out/src/gds/$cell.gds.gz
  fi
  echo "$gds_in" > gds_checked.txt

  # 2. Magic DRC (full rule style) and hierarchical LVS extraction.
  cat > magic_drc_ext.tcl <<EOS
crashbackups stop
addpath $out/src/magic
addpath $out/src/magic/paramcells
load $cell
select top cell
drc euclidean on
drc style drc(full)
drc check
drc catchup
set n [drc list count total]
puts "MAGIC_DRC_COUNT \$n"
set fh [open $out/magic_drc.txt w]
puts \$fh "style: [drc list style]"
puts \$fh "total: \$n"
foreach {why boxes} [drc listall why] { puts \$fh "\$why : [llength \$boxes]" }
close \$fh
extract path $out/ext_lvs
extract do unique
extract no all
extract all
ext2spice lvs
ext2spice -p $out/ext_lvs -o $out/layout_lvs.spice
quit -noprompt
EOS
  mkdir -p ext_lvs ext_pex
  magic -dnull -noconsole -rcfile $MAGICRC magic_drc_ext.tcl > magic.log 2>&1 < /dev/null
  echo "magic_drc_lvs_exit $?" > magic_status.txt

  # 3. Parasitic extraction in separate Magic runs: R+C preferred, C-only fallback.
  pex_script "$out" "$cell" resistance > magic_pex_rc.tcl
  magic -dnull -noconsole -rcfile $MAGICRC magic_pex_rc.tcl > magic_pex_rc.log 2>&1 < /dev/null
  rc=$?
  if [ $rc -eq 0 ] && [ -s layout_pex.spice ]; then
    echo rc > pex_mode.txt
  else
    echo "rc_extraction_exit $rc" > pex_rc_failure.txt
    rm -rf ext_pex layout_pex.spice; mkdir -p ext_pex
    pex_script "$out" "$cell" none > magic_pex_c.tcl
    magic -dnull -noconsole -rcfile $MAGICRC magic_pex_c.tcl > magic_pex_c.log 2>&1 < /dev/null
    if [ -s layout_pex.spice ]; then echo c_only > pex_mode.txt; else echo failed > pex_mode.txt; fi
  fi

  # 4. Netgen LVS: Magic extraction vs regenerated schematic + std-cell netlists.
  #    Both sides get the canonical MIM orientation (canon_mim.py: c_width >=
  #    c_length, exact swap only) because Magic reports a rotated cap_mim
  #    paramcell transposed between hierarchical and flat extraction.
  python3 /src/flow/canon_mim.py "$schnet" $out/sch_lvs.spice > canon_mim.log
  schnet=$out/sch_lvs.spice
  python3 /src/flow/canon_mim.py $out/layout_lvs.spice $out/layout_lvs.spice >> canon_mim.log
  cat > netgen.tcl <<EOS
set circuit1 [readnet spice $out/layout_lvs.spice]
set circuit2 [readnet spice $PDK_ROOT/$PDK/libs.ref/$SCLIB/spice/$SCLIB.spice]
readnet spice $schnet \$circuit2
lvs "\$circuit1 $cell" "\$circuit2 $cell" $PDK_ROOT/$PDK/libs.tech/netgen/${PDK}_setup.tcl $out/lvs_comp.out
EOS
  NETGEN_COLUMNS=75 netgen -batch source netgen.tcl > netgen.log 2>&1 < /dev/null

  # 4b. Diagnostic LVS with the die's single ground applied (dvss tied to avss
  #     in both netlists).  Reported separately; it does not replace step 4.
  if [ "$base" = biasgen ]; then
    python3 /src/flow/tie_nets.py $schnet $out/sch_tiedgnd.spice $cell dvss avss
    python3 /src/flow/tie_nets.py $out/layout_lvs.spice $out/layout_tiedgnd.spice $cell dvss avss
    sed -e "s#$out/layout_lvs.spice#$out/layout_tiedgnd.spice#" -e "s#$schnet#$out/sch_tiedgnd.spice#" \
        -e "s#$out/lvs_comp.out#$out/lvs_comp_tiedgnd.out#" netgen.tcl > netgen_tiedgnd.tcl
    NETGEN_COLUMNS=75 netgen -batch source netgen_tiedgnd.tcl > netgen_tiedgnd.log 2>&1 < /dev/null
  fi

  # 4c. LVS of the GDS stream itself (the tapeout deliverable): read back into
  #     Magic, flattened so connectivity comes only from mask geometry (no
  #     reliance on subcell port equivalence), then compared with the schematic.
  mkdir -p ext_gds
  cat > magic_gds_ext.tcl <<EOS
crashbackups stop
drc off
gds readonly true
gds read $gds_in
load $cell
flatten ${cell}_flat
load ${cell}_flat
select top cell
extract path $out/ext_gds
extract no all
extract all
ext2spice lvs
ext2spice -p $out/ext_gds -o $out/layout_gds_flat.spice
quit -noprompt
EOS
  ( cd ext_gds && magic -dnull -noconsole -rcfile $MAGICRC ../magic_gds_ext.tcl > ../magic_gds.log 2>&1 < /dev/null )
  sed -i "s/^\.subckt ${cell}_flat /.subckt $cell /" layout_gds_flat.spice 2>/dev/null
  python3 /src/flow/canon_mim.py $out/layout_gds_flat.spice $out/layout_gds_flat.spice >> canon_mim.log
  sed -e "s#$out/layout_lvs.spice#$out/layout_gds_flat.spice#" -e "s#$out/lvs_comp.out#$out/lvs_gds_comp.out#" \
      netgen.tcl > netgen_gds.tcl
  NETGEN_COLUMNS=75 netgen -batch source netgen_gds.tcl > netgen_gds.log 2>&1 < /dev/null
  if [ "$base" = biasgen ]; then
    python3 /src/flow/tie_nets.py $out/layout_gds_flat.spice $out/layout_gds_tiedgnd.spice $cell dvss avss
    sed -e "s#$out/layout_tiedgnd.spice#$out/layout_gds_tiedgnd.spice#" \
        -e "s#$out/lvs_comp_tiedgnd.out#$out/lvs_gds_comp_tiedgnd.out#" netgen_tiedgnd.tcl > netgen_gds_tiedgnd.tcl
    NETGEN_COLUMNS=75 netgen -batch source netgen_gds_tiedgnd.tcl > netgen_gds_tiedgnd.log 2>&1 < /dev/null
  fi

  # 5. KLayout DRC on the checked GDS (upstream invocation, density excluded).
  if [ "$KLAYOUT_DRC" = 1 ]; then
    klayout -b -zz -r $PDK_ROOT/$PDK/libs.tech/klayout/tech/drc/gf180mcu.drc \
      -rd input=$gds_in -rd report=$out/klayout_drc.lyrdb \
      -rd feol=True -rd beol=True -rd conn_drc=True -rd wedge=True -rd run_mode=deep \
      -rd decks=all,-density -rd thr=${KLAYOUT_THREADS:-4} -rd topcell=$cell \
      > klayout_drc.log 2>&1 < /dev/null
  fi
  # 5b. XOR of an exported variant against the vendored upstream GDS
  if [ "$blk" != "$base" ]; then
    klayout -b -r /src/flow/gds_xor.py -rd ga=$out/src/gds/$cell.gds.gz -rd gb=$gds_in -rd top=$cell \
      -rd out=$out/xor_vs_vendored.json > xor.log 2>&1 < /dev/null
  fi

  # 5c. Bandgap only: this PDK's Magic tech names the PDK's fixed 5x5 um PNP cell
  #     (pnp_05p00x05p00_0, emitter 5 x 5 um) pnp_10p00x00p42.  Diagnostic LVS with that
  #     device name mapped back; the plain LVS above stays the primary result.
  if [ "$base" = bandgap ]; then
    for v in lvs gds; do
      l=$([ $v = lvs ] && echo layout_lvs.spice || echo layout_gds_flat.spice)
      sed 's/pnp_10p00x00p42/pnp_05p00x05p00/g' $l > ${l%.spice}_pnpalias.spice
      sed -e "s#$out/$l#$out/${l%.spice}_pnpalias.spice#" -e "s#$out/lvs_comp.out#$out/${v}_comp_pnpalias.out#" \
          -e "s#$out/lvs_gds_comp.out#$out/${v}_comp_pnpalias.out#" \
          $([ $v = lvs ] && echo netgen.tcl || echo netgen_gds.tcl) > netgen_${v}_pnpalias.tcl
      NETGEN_COLUMNS=75 netgen -batch source netgen_${v}_pnpalias.tcl > netgen_${v}_pnpalias.log 2>&1 < /dev/null
    done
  fi

  # 6. HRES (62/0) coverage of every ppolyf_u_1k body in the checked GDS
  #    (spec/block-deliverables.md "GDS export rule").
  klayout -b -r /src/flow/hres_check.py -rd gds=$gds_in -rd top=$cell -rd out=$out/hres_check.json \
    > hres_check.log 2>&1 < /dev/null
  echo "$blk clean flow done"
done
