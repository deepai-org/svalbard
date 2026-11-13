#!/bin/bash
# audit: re-extract the PUBLISHED aosc.gds and compare with the LVS netlist recorded in aosc-evidence.json
set -e
cd /work/lvs
rm -rf aosc && mkdir aosc && cd aosc
cp /proj/analog/timing/generated/aosc.gds .
magic -dnull -noconsole -rcfile $PDKPATH/libs.tech/magic/gf180mcuD.magicrc <<EOF > magic.log 2>&1
gds read aosc.gds
load pt_aosc
select top cell
extract do local
extract all
ext2spice lvs
ext2spice -o aosc_gds.spice
quit -noprompt
EOF
grep -c "" aosc_gds.spice
netgen -batch lvs "aosc_gds.spice pt_aosc" "/proj/analog/timing/generated/aosc.lvs.spice pt_aosc" $PDKPATH/libs.tech/netgen/gf180mcuD_setup.tcl comp.out > netgen.log 2>&1 || true
tail -4 comp.out
