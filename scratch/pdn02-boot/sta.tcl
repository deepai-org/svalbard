# PDN-02 boot-path STA: routed delivered macro (DG9-29 pt_rf / DG9-30 pt_wired), max or min SPEF, characterized lib,
# optional uniform cell-delay factor K (supply droop), HOST_RATE_DIV RATE. Clock network keeps the SDC OCV (x1.08/0.92).
read_liberty /clib/gf180mcu_fd_sc_mcu7t5v0__$::env(LIBPVT).lib
read_verilog /mrun/final/pnl/pt_digital_macro.pnl.v
link_design pt_digital_macro
read_spef /mrun/final/spef/$::env(RC)/pt_digital_macro.$::env(RC).spef
set PT_TIMING_CORNER $::env(TC)
set PT_LIB_CHARACTERIZED 1
set HOST_RATE_DIV $::env(RATE)
if {[info exists ::env(HWP)] && $::env(HWP) ne ""} { set HWORD_PERIOD $::env(HWP) }
source /sdc/pt_digital_macro.sdc
set_propagated_clock [all_clocks]
catch {sta::set_recovery_removal_checks_enabled 1}
set d $::env(K)
if {$d != 1.0} {
  set_timing_derate -late -cell_delay -data $d ; set_timing_derate -early -cell_delay -data $d
  set_timing_derate -late -cell_delay -clock [expr {$d*1.08}] ; set_timing_derate -early -cell_delay -clock [expr {$d*0.92}]
}
set dly $::env(DLY)
puts "PT_WS [sta::worst_slack_cmd $dly]"
foreach c [all_clocks] {
  set ps [find_timing_paths -path_delay $dly -group_path_count 1 -sort_by_slack -to $c]
  if {[llength $ps]} { set p [lindex $ps 0]; puts "PT_CLK [get_name $c] [format %.3f [get_property $p slack]] [get_full_name [get_property $p startpoint]] -> [get_full_name [get_property $p endpoint]]" }
}
