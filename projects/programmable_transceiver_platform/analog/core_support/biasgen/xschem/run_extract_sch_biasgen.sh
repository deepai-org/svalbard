#!/bin/bash
mkdir -p ../netlist/schematic

project=gf180mcu_ocd_ip__biasgen

export PDK_ROOT=${PDK_ROOT:-/usr/share/pdk}
export PDK=${PDK:-gf180mcuD}

# xschem -n -s -r -x -q --tcl "set top_is_subckt 1" --rcfile $PDK_ROOT/$PDK/libs.tech/xschem/xschemrc -o ../netlist/schematic -N $project.spice $project.sch
xschem -n -s -r -x -q --tcl "set top_is_subckt 1" --rcfile ./xschemrc -o ../netlist/schematic -N $project.spice $project.sch

echo "Done!"
exit 0
