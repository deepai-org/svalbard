#!/bin/bash
mkdir -p ../netlist/schematic

project=gf180mcu_ocd_ip__bandgap

export PDK_ROOT=${PDK_ROOT:-/usr/share/pdk}
export PDK=${PDK:-gf180mcuD}

# NOTE:  The xschemrc in this directory sets up the correct link
# to the Avalon Semiconductors standard cell library.

# xschem -n -s -r -x -q --tcl "set top_is_subckt 1" --rcfile $PDK_ROOT/$PDK/libs.tech/xschem/xschemrc -o ../netlist/schematic -N $project.spice $project.sch
xschem -n -s -r -x -q --tcl "set top_is_subckt 1" --rcfile ./xschemrc -o ../netlist/schematic -N $project.spice $project.sch

echo "Done!"
exit 0
