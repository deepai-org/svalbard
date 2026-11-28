# detail.tcl: full path reports for chosen clocks on a routed macro (env LIBPVT RC TC RATE K CLKS NP)
read_liberty /clib/gf180mcu_fd_sc_mcu7t5v0__$::env(LIBPVT).lib
read_verilog /mrun/final/pnl/pt_digital_macro.pnl.v
link_design pt_digital_macro
read_spef /mrun/final/spef/$::env(RC)/pt_digital_macro.$::env(RC).spef
set PT_TIMING_CORNER $::env(TC)
set PT_LIB_CHARACTERIZED 1
set HOST_RATE_DIV $::env(RATE)
source /sdc/pt_digital_macro.sdc
set_propagated_clock [all_clocks]
catch {sta::set_recovery_removal_checks_enabled 1}
set d $::env(K)
if {$d != 1.0} {
  set_timing_derate -late -cell_delay -data $d ; set_timing_derate -early -cell_delay -data $d
  set_timing_derate -late -cell_delay -clock [expr {$d*1.08}] ; set_timing_derate -early -cell_delay -clock [expr {$d*0.92}]
}
foreach c $::env(CLKS) {
  report_checks -path_delay max -to [get_clocks $c] -group_path_count $::env(NP) -endpoint_path_count 1 -fields {fanout cap slew} -format full_clock_expanded -digits 3
}
