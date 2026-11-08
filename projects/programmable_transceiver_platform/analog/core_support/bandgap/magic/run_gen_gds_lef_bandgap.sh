#!/bin/bash
#
# Run GDS and LEF generation on the bandgap
#
export PDK_ROOT=${PDK_ROOT:-/usr/share/pdk}
export PDK=${PDK:-gf180mcuD}

PROJECT=gf180mcu_ocd_ip__bandgap

echo "Running GDS and LEF generation on ${project}"
magic -dnull -noconsole -rcfile ${PDK_ROOT}/${PDK}/libs.tech/magic/${PDK}.magicrc << EOF
# Read the standard cells from foundry GDS
gds read ${PDK_ROOT}/${PDK}/libs.ref/gf180mcu_as_sc_mcu7t3v3/gds/gf180mcu_as_sc_mcu7t3v3.gds 
load ${PROJECT}
select top cell
expand
select top cell
gds compress 9
gds write ${PROJECT}
select top cell
lef write -hide
quit -noprompt
EOF
rm -rf extfiles
mv ${PROJECT}.gds.gz ../gds/
mv ${PROJECT}.lef ../lef/
echo "Done"
