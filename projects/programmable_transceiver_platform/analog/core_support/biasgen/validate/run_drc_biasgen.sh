#!/bin/bash
#
# Run klayout DRC on the current bias generator
#
export PDK_ROOT=${PDK_ROOT:-/usr/share/pdk}
export PDK=${PDK:-gf180mcuD}

export PDK_GEN=gf180mcu

export PROJECT=gf180mcu_ocd_ip__biasgen

klayout -b -zz -r ${PDK_ROOT}/${PDK}/libs.tech/klayout/tech/drc/${PDK_GEN}.drc -rd input=../gds/${PROJECT}.gds.gz -rd report=../validate/${PROJECT}.lyrdb -rd feol=True -rd beol=True -rd conn_drc=True -rd wedge=True -rd run_mode=deep -rd decks=all,-density -rd thr=16 -rd topcell=${PROJECT}

echo "Done!"
exit 0
