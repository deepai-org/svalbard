create_clock -name wr_clk -period 25.6 [get_ports wr_clk]
create_clock -name rd_clk -period 25.6 [get_ports rd_clk]
set_propagated_clock [all_clocks]
set_clock_uncertainty -hold 0.5 [all_clocks]
# Provisional internal block-interface budgets, not measured source timing.
set_input_delay -max 4 -clock wr_clk [get_ports {wr_data* wr_words* wr_valid}]
set_input_delay -min 0 -clock wr_clk [get_ports {wr_data* wr_words* wr_valid}]
set_input_delay -max 4 -clock rd_clk [get_ports rd_ready]
set_input_delay -min 0 -clock rd_clk [get_ports rd_ready]
set_output_delay -max 4 -clock wr_clk [get_ports {wr_ready wr_fault}]
set_output_delay -min 0 -clock wr_clk [get_ports {wr_ready wr_fault}]
set_output_delay -max 4 -clock rd_clk [get_ports {rd_valid rd_data* rd_words*}]
set_output_delay -min 0 -clock rd_clk [get_ports {rd_valid rd_data* rd_words*}]
set_input_transition 0.5 [get_ports {wr_data* wr_words* wr_valid rd_ready}]
set_load 0.005 [all_outputs]
# Report only same-domain paths. Cross-domain paths are NOT declared safe.
foreach domain {wr_clk rd_clk} {
 foreach delay {max min} {
  puts "DOMAIN_BEGIN $domain $delay"
  report_checks -from [get_clocks $domain] -to [get_clocks $domain] -path_delay $delay -group_path_count 3 -digits 4
  puts "DOMAIN_END $domain $delay"
 }
}
puts "CONSTRAINT_BEGIN"
check_setup -verbose
puts "CONSTRAINT_END"
puts "ELECTRICAL_BEGIN"
report_check_types -max_slew -max_capacitance -violators
puts "ELECTRICAL_END"
exit
