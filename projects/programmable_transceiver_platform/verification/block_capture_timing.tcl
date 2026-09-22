read_liberty /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib
read_verilog /out/mapped.v
link_design pt_block_fifo_capture
create_clock -name wr_clk -period 25.6 [get_ports wr_clk]
create_clock -name rd_clk -period 25.6 [get_ports rd_clk]
# Illustrative internal boundary allocations, not finalized external IO timing.
set_input_delay 4 -clock wr_clk [get_ports {wr_data* wr_words* wr_valid}]
set_input_delay 4 -clock rd_clk [get_ports rd_ready]
set_output_delay 4 -clock wr_clk [get_ports {wr_ready wr_fault}]
set_output_delay 4 -clock rd_clk [get_ports {rd_valid captured*}]
set_input_transition 0.5 [get_ports {wr_data* wr_words* wr_valid rd_ready}]
set_load 0.005 [all_outputs]
source /out/capture-pins.tcl
if {[llength $capture_pins] != 84} {error "Missing capture endpoints"}
# Budget the bundled data path without pretending clocks have a known phase.
# Compliance with this budget is not a CDC proof or a justified stability window.
set_max_delay 25.6 -ignore_clock_latency -from [get_clocks wr_clk] -to $capture_pins
foreach name {wr_clk rd_clk} {
 puts "CAPTURE_BEGIN $name"
 report_checks -from [get_clocks $name] -to $capture_pins -path_delay max -group_path_count 1 -digits 4
 puts "CAPTURE_END $name"
}
puts "POINTER_BEGIN"
report_checks -from $pointer_pins -to $capture_pins -path_delay max -group_path_count 1 -digits 4
puts "POINTER_END"
puts "ELECTRICAL_BEGIN"
report_check_types -max_slew -max_capacitance -violators
puts "ELECTRICAL_END"
check_setup -verbose
exit
