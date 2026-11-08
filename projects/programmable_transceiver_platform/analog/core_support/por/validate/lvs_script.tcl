# Tcl script for setting up LVS for the gf180mcu 3.3V PoR

if {[catch {set PDK_ROOT $::env(PDK_ROOT)}]} {set PDK_ROOT /usr/share/pdk} 
if {[catch {set PDK $::env(PDK)}]} {set PDK gf180mcuD}

set circuit2 [readnet spice ${PDK_ROOT}/${PDK}/libs.ref/gf180mcu_as_sc_mcu7t3v3/spice/gf180mcu_as_sc_mcu7t3v3.spice]
readnet spice ../netlist/schematic/gf180mcu_ocd_ip__por.spice $circuit2

set circuit1 [readnet spice ../netlist/layout/gf180mcu_ocd_ip__por.spice]

lvs "$circuit1 gf180mcu_ocd_ip__por" "$circuit2 gf180mcu_ocd_ip__por" \
${PDK_ROOT}/${PDK}/libs.tech/netgen/${PDK}_setup.tcl gf180mcu_ocd_ip__por_comp.out
