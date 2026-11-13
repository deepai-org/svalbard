#!/bin/bash
# audit: re-run GDS-level LVS of the vendored POR GDS (tapeout source) against the vendored schematic netlist
set -e
cell=gf180mcu_ocd_ip__por
SCLIB=gf180mcu_as_sc_mcu7t3v3
cd /work/lvs; rm -rf por && mkdir por && cd por
gunzip -c /proj/analog/core_support/por/gds/$cell.gds.gz > $cell.gds
sha256sum $cell.gds
magic -dnull -noconsole -rcfile $PDKPATH/libs.tech/magic/gf180mcuD.magicrc <<EOF > magic.log 2>&1
crashbackups stop
drc off
gds read $cell.gds
load $cell
flatten ${cell}_flat
load ${cell}_flat
select top cell
extract do local
extract no all
extract all
ext2spice lvs
ext2spice -o layout_gds_flat.spice
quit -noprompt
EOF
sed -i "s/^\.subckt ${cell}_flat /.subckt $cell /" layout_gds_flat.spice
python3 /proj/analog/core_support/flow/canon_mim.py layout_gds_flat.spice layout_gds_flat.spice > canon.log
python3 /proj/analog/core_support/flow/canon_mim.py /proj/analog/core_support/por/netlist/schematic/$cell.spice sch.spice >> canon.log
cat > netgen.tcl <<EOS
set circuit1 [readnet spice layout_gds_flat.spice]
set circuit2 [readnet spice $PDKPATH/libs.ref/$SCLIB/spice/$SCLIB.spice]
readnet spice sch.spice \$circuit2
lvs "\$circuit1 $cell" "\$circuit2 $cell" $PDKPATH/libs.tech/netgen/gf180mcuD_setup.tcl lvs_comp.out
EOS
NETGEN_COLUMNS=75 netgen -batch source netgen.tcl > netgen.log 2>&1 < /dev/null || true
tail -4 lvs_comp.out; grep -c -i "property error\|failed pin matching\|do not match" lvs_comp.out || true
