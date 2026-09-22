# Provisional local digital grid; not chip/pad power delivery or EM sizing.
read_db /input/supply-connected.odb
set_voltage_domain -name CORE -power VDD_CORE -ground VSS_CORE
define_pdn_grid -name digital -voltage_domains {CORE} -pins {Metal3}
# Native cell VDD/VSS rails are 0.6 um wide on Metal1.
add_pdn_stripe -grid digital -layer Metal1 -width 0.6 -followpins
add_pdn_stripe -grid digital -layer Metal2 -width 2.0 -pitch 80 -offset 10
add_pdn_stripe -grid digital -layer Metal3 -width 4.0 -pitch 80 -offset 10
add_pdn_connect -grid digital -layers {Metal1 Metal2}
add_pdn_connect -grid digital -layers {Metal2 Metal3}
pdngen -failed_via_report /out/failed-vias.rpt
check_power_grid -net VDD_CORE -error_file /out/vdd-connectivity.rpt
check_power_grid -net VSS_CORE -error_file /out/vss-connectivity.rpt
check_placement -verbose
write_db /out/digital-pdn.odb
write_def /out/digital-pdn.def
puts "PDN_SCREEN_COMPLETE"
exit
