#!/bin/bash
#
# Run GDS and LEF generation on the 3.3V PoR
#
echo ${PDK_ROOT:=/usr/share/pdk} > /dev/null
echo ${PDK:=gf180mcuD} > /dev/null
project=gf180mcu_ocd_ip__por

echo "Running GDS and LEF generation on ${project}"
magic -dnull -noconsole -rcfile ${PDK_ROOT}/${PDK}/libs.tech/magic/${PDK}.magicrc << EOF
load ${project}
select top cell
expand
select top cell
gds compress 9
gds write ${project}
select top cell
lef write -hide
quit -noprompt
EOF
rm -rf extfiles
mv ${project}.gds.gz ../gds/
mv ${project}.lef ../lef/
echo "Done"
