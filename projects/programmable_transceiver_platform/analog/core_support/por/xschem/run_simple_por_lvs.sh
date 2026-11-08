#!/bin/bash
#---------------------------------------------------------------------------
#
# Run LVS on the GF180MCU PoR (improved, self-biased version).
#
#---------------------------------------------------------------------------
echo ${PDK_ROOT:=/usr/share/pdk} > /dev/null
echo ${PDK:=gf180mcuD} > /dev/null

project=gf180mcu_ocd_ip__por

sclib=gf180mcu_as_sc_mcu7t3v3

# Extract full layout netlist
cd ../magic
if [ ! -f ../netlist/layout/${project}.spice ]; then
magic -dnull -noconsole -rcfile $PDK_ROOT/$PDK/libs.tech/magic/$PDK.magicrc << EOF
drc off
crashbackups stop
load ${project}
extract path extfiles
extract do unique
extract all
ext2spice lvs
ext2spice -p extfiles -o ../netlist/layout/${project}.spice
EOF
rm -rf extfiles
fi
cd ../xschem

# Generate script for netgen
cat > netgen.tcl << EOF
# Load top level netlist
puts stdout "Reading layout ${project}.spice"
set circuit1 [readnet spice ../netlist/layout/${project}.spice]
puts stdout "Reading schematic netlist ${project}.spice"
set circuit2 [readnet spice ${project}.spice]
# Read additional subcircuits into the netlist of circuit2
puts stdout "Reading standard cell netlists"
readnet spice $PDK_ROOT/$PDK/libs.ref/${sclib}/spice/${sclib}.spice \$circuit2

# Run LVS
lvs "\$circuit1 ${project}" "\$circuit2 ${project}" $PDK_ROOT/$PDK/libs.tech/netgen/${PDK}_setup.tcl ${project}_comp.out
EOF

export NETGEN_COLUMNS=60
netgen -batch source netgen.tcl
rm netgen.tcl

exit 0
