read_liberty /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib
read_verilog /out/mapped.v
link_design pt_block_fifo
# Conservative candidate host block rate in both domains. Clocks remain ideal.
create_clock -name wr_clk -period 25.6 [get_ports wr_clk]
create_clock -name rd_clk -period 25.6 [get_ports rd_clk]
foreach name {wr_clk rd_clk} {
 puts "DOMAIN_BEGIN $name"
 report_checks -from [get_clocks $name] -to [get_clocks $name] -path_delay max -group_path_count 3 -digits 4
 puts "DOMAIN_END $name"
}
puts "ELECTRICAL_BEGIN"
report_check_types -max_slew -max_capacitance -violators
puts "ELECTRICAL_END"
puts "CONSTRAINT_BEGIN"
check_setup -verbose
puts "CONSTRAINT_END"
exit
