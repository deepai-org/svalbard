read_liberty /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib
read_verilog /out/mapped.v
link_design pt_block_elastic
create_clock -name wr_clk -period 25.6 [get_ports wr_clk]
create_clock -name rd_clk -period 25.6 [get_ports rd_clk]
source /out/pins.tcl
if {[llength $capture_pins] != 168 || [llength $full_pin] != 1} {error "Missing pins"}
foreach delay {max min} {
 puts "CAPACITY_BEGIN $delay"
 report_checks -from $full_pin -to $capture_pins -path_delay $delay -group_path_count 200 -endpoint_path_count 1 -digits 4
 puts "CAPACITY_END $delay"
}
puts "ELECTRICAL_BEGIN"
report_check_types -max_slew -max_capacitance -violators
puts "ELECTRICAL_END"
exit
