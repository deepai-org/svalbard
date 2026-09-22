read_liberty /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib
read_verilog /out/mapped.v
link_design pt_block_rx
create_clock -name clk -period 25.6 [get_ports clk]
# Provisional internal beat interface, not package/DDR constraints.
set_input_delay -max 4 -clock clk [get_ports {words* in_valid wire_ready iq_ready command_ready}]
set_input_delay -min 0 -clock clk [get_ports {words* in_valid wire_ready iq_ready command_ready}]
set_input_transition 0.5 [get_ports {words* in_valid wire_ready iq_ready command_ready}]
set_output_delay -max 4 -clock clk [all_outputs]
set_output_delay -min 0 -clock clk [all_outputs]
set_load 0.005 [all_outputs]
# Mode is constant while running; screen both explicitly, not a false-path blanket.
foreach mode {0 1} {
 set_case_analysis $mode [get_ports mode8]
 foreach delay {max min} {
  puts "PATH_BEGIN $mode $delay"
  report_checks -path_delay $delay -group_path_count 3 -digits 4
  puts "PATH_END $mode $delay"
 }
}
puts "ELECTRICAL_BEGIN"
report_check_types -max_slew -max_capacitance -violators
puts "ELECTRICAL_END"
puts "CONSTRAINT_BEGIN"
check_setup -verbose
puts "CONSTRAINT_END"
exit
