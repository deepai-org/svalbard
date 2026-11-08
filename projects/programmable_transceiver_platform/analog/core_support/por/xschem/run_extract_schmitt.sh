#!/bin/bash
mkdir -p ../netlist/schematic

project=por_3v3_schmitt_inv

echo ${PDK_ROOT:=/usr/share/pdk} > /dev/null
echo ${PDK:=gf180mcuD} > /dev/null

# xschem -n -s -r -x -q --tcl "set top_is_subckt 1" --rcfile $PDK_ROOT/$PDK/libs.tech/xschem/xschemrc -o ../netlist/schematic -N $project.spice $project.sch

# Note:  The local xschemrc file adds the standard cell library to the path.

xschem -n -s -r -x -q --tcl "set top_is_subckt 1" --rcfile ./xschemrc -o ../netlist/schematic -N $project.spice $project.sch

echo "Done!"
exit 0
