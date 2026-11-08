#!/bin/bash
#
# Run klayout DRC on the 3.3V PoR
# GDS is gf180mcu_ocd_ip__por.gds.gz, top level cell name is
# gf180mcu_ocd_ip__por
#
echo ${PDK_ROOT:=/usr/share/pdk} > /dev/null
echo ${PDK:=gf180mcuD} > /dev/null

klayout -b -zz -r ${PDK_ROOT}/${PDK}/libs.tech/klayout/tech/drc/gf180mcu.drc -rd input=../gds/gf180mcu_ocd_ip__por.gds.gz -rd report=../validate/gf180mcu_ocd_ip__por_drc_klayout.lyrdb -rd feol=True -rd beol=True -rd conn_drc=True -rd wedge=True -rd decks=all,-density -rd run_mode=deep -rd thr=16 -rd topcell=gf180mcu_ocd_ip__por

echo "Done!"
exit 0
