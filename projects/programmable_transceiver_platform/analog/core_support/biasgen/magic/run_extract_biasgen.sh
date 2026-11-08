#!/bin/bash
#
# Run layout extraction on the bias generator
#
export PDK_ROOT=${PDK_ROOT:-/usr/share/pdk}
export PDK=${PDK:-gf180mcuD}

project=gf180mcu_ocd_ip__biasgen

echo "Running netlist extraction on $project"
magic -dnull -noconsole -rcfile ${PDK_ROOT}/${PDK}/libs.tech/magic/${PDK}.magicrc << EOF
addpath ../../../magic/gf180mcu_as_sc_mcu7t3v3
load $project
select top cell
extract path extfiles
extract do unique
extract no all
extract all
ext2spice lvs
ext2spice -p extfiles -o ../netlist/layout/${project}.spice
quit -noprompt
EOF
rm -rf extfiles
echo "Done"
