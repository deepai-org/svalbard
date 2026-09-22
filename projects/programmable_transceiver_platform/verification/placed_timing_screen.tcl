# Same placed database, with and without estimated signal interconnect.
read_liberty /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib
read_db /out/digital.odb
foreach {port period} {host_tx_clk 3.2 host_rx_clk 3.2 wire_rx_clk 4.0 wire_tx_clk 4.0 rf_rx_clk 50.0 rf_tx_clk 50.0 host_sclk 100.0 ref_clk 25.0} {
 create_clock -name $port -period $period [get_ports $port]
}
if {$::env(PT_ESTIMATE) == 1} {
 set_wire_rc -signal -layer Metal3
 estimate_parasitics -placement
}
# Clocks stay ideal: this isolates the signal-wire effect, not CTS qualification.
foreach name {host_tx_clk host_rx_clk wire_rx_clk wire_tx_clk rf_rx_clk rf_tx_clk host_sclk ref_clk} {
 puts "DOMAIN_BEGIN $name"
 report_checks -from [get_clocks $name] -to [get_clocks $name] -path_delay max -group_path_count 3 -format full_clock_expanded -digits 4
 puts "DOMAIN_END $name"
}
puts "ELECTRICAL_AUDIT_BEGIN"
report_check_types -max_slew -max_capacitance -violators
puts "ELECTRICAL_AUDIT_END"
puts "CONSTRAINT_AUDIT_BEGIN"
check_setup -verbose
puts "CONSTRAINT_AUDIT_END"
exit
