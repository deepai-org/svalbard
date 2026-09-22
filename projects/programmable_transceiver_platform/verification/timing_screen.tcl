# Early same-domain register timing only. No CDC exceptions or physical timing closure claimed.
set lib /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib
read_liberty $lib
read_verilog /out/pt_digital_mapped.v
link_design pt_digital
set mode $::env(PT_MODE)
if {$mode == 0} { set hp 4.0; set wp 8.0; set rp 25.0 } else { set hp 3.2; set wp 4.0; set rp 50.0 }
# SPI/reference rates are illustrative service rates, not finalized analog clock requirements.
foreach {port period} [list host_tx_clk $hp host_rx_clk $hp wire_rx_clk $wp wire_tx_clk $wp rf_rx_clk $rp rf_tx_clk $rp host_sclk 100.0 ref_clk 25.0] {
 create_clock -name $port -period $period [get_ports $port]
}
# Ideal clocks and no extracted interconnect. Unbuffered high-fanout nets can also
# cause unrealistic extrapolated delays; this is not a lower or upper timing bound.
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
