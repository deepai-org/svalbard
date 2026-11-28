# summ.tcl: per-clock worst setup (max) or hold (min) slack, failing endpoint count, worst path; env as detail.tcl + DLY
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
  set ps [find_timing_paths -path_delay $dly -group_path_count 5000 -endpoint_path_count 1 -sort_by_slack -slack_max 0.0 -to $c]
  set n [llength $ps]; set tns 0.0
  foreach q $ps { set tns [expr {$tns + [get_property $q slack]}] }
  set all [find_timing_paths -path_delay $dly -group_path_count 1 -sort_by_slack -to $c]
  if {[llength $all]} { set p [lindex $all 0]; puts "PT_CLK [get_name $c] [format %.3f [get_property $p slack]] nfail=$n tns=[format %.2f $tns] [get_full_name [get_property $p startpoint]] -> [get_full_name [get_property $p endpoint]]" }
}
