#!/bin/sh
#
# Run LVS on the gf180mcu 3.3V PoR (gf180mcu_ocd_ip__por)
#
echo ${PDK_ROOT:=/usr/share/pdk} > /dev/null
echo ${PDK:=gf180mcuD} > /dev/null

# export NETGEN_COLUMNS=150
export NETGEN_COLUMNS=75

netgen -batch source lvs_script.tcl
