# Provisional local digital grid; not chip/pad power delivery or EM sizing.
read_db /input/supply-connected.odb
set_voltage_domain -name CORE -power VDD_CORE -ground VSS_CORE
define_pdn_grid -name digital -voltage_domains {CORE} -pins {Metal5}
# Native cell VDD/VSS rails are 0.6 um wide on Metal1.
add_pdn_stripe -grid digital -layer Metal1 -width 0.6 -followpins
add_pdn_stripe -grid digital -layer Metal4 -width 2.0 -pitch 80 -offset 10
add_pdn_stripe -grid digital -layer Metal5 -width 4.0 -pitch 80 -offset 10
add_pdn_connect -grid digital -layers {Metal1 Metal4}
add_pdn_connect -grid digital -layers {Metal4 Metal5}
pdngen -failed_via_report /out/failed-vias.rpt
check_power_grid -net VDD_CORE -error_file /out/vdd-connectivity.rpt
check_power_grid -net VSS_CORE -error_file /out/vss-connectivity.rpt
check_placement -verbose
write_db /out/digital-pdn.odb
write_def /out/digital-pdn.def
set metrics [open /out/grid-shapes.tsv w]
foreach name {VDD_CORE VSS_CORE} {
 set net [[ord::get_db_block] findNet $name]
 foreach swire [$net getSWires] {
  foreach shape [$swire getWires] {
   if {[$shape isVia]} {puts $metrics "$name\tVIA"} else {
    puts $metrics "$name\t[[$shape getTechLayer] getName]"
   }
  }
 }
}
close $metrics
puts "PDN_SCREEN_COMPLETE"
exit
