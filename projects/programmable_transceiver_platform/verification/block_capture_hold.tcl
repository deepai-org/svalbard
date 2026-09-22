read_liberty /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib
read_verilog /mapped/mapped.v
link_design pt_block_fifo_capture
create_clock -name wr_clk -period 25.6 [get_ports wr_clk]
create_clock -name rd_clk -period 25.6 [get_ports rd_clk]
# Earliest ready arrival is zero; pass 59's 4 ns maximum is not a hold budget.
set_input_delay -min 0 -clock rd_clk [get_ports rd_ready]
set_input_transition 0.5 [get_ports rd_ready]
set_load 0.005 [get_ports captured*]
source /mapped/capture-pins.tcl
if {[llength $capture_pins] != 84 || [llength $pointer_pins] != 4} {error "Missing endpoints"}
set feedback_pins {}
foreach pin $capture_pins {
 set name [get_full_name $pin]
 regsub {/D$} $name {/Q} name
 lappend feedback_pins {*}[get_pins $name]
}
foreach {label pins} [list pointer $pointer_pins feedback $feedback_pins ready [get_ports rd_ready] read_domain [get_clocks rd_clk]] {
 puts "HOLD_BEGIN $label"
 report_checks -from $pins -to $capture_pins -path_delay min -group_path_count 100 -endpoint_path_count 1 -digits 4
 puts "HOLD_END $label"
}
# Sensitivity controls, not a claimed CTS budget.
foreach uncertainty {0.5 5.0} {
 set_clock_uncertainty -hold $uncertainty [get_clocks rd_clk]
 puts "SENSITIVITY_BEGIN $uncertainty"
 report_checks -from [get_clocks rd_clk] -to $capture_pins -path_delay min -group_path_count 1 -digits 4
 puts "SENSITIVITY_END $uncertainty"
}
exit
