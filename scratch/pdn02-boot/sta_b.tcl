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
foreach c {sclk hword hddr hsdr hcore h2d h2d_cap mon_host egress_mem_sclk ref} {
  if {![llength [get_clocks -quiet $c]]} continue
  foreach dly {max min} {
    set ps [find_timing_paths -path_delay $dly -group_path_count 1 -endpoint_path_count 1 -sort_by_slack -from [get_clocks $c] -to [get_clocks $c]]
    if {[llength $ps]} { set p [lindex $ps 0]; puts "PT_INTRA $dly $c [format %.3f [get_property $p slack]] [get_full_name [get_property $p startpoint]] -> [get_full_name [get_property $p endpoint]]" }
  }
  set ps [find_timing_paths -path_delay max -group_path_count 200 -endpoint_path_count 1 -sort_by_slack -slack_max 0 -to [get_clocks $c]]
  puts "PT_NVIOL $c [llength $ps]"
  foreach p [lrange $ps 0 7] { puts "PT_V $c [format %.3f [get_property $p slack]] [get_full_name [get_property $p startpoint]] -> [get_full_name [get_property $p endpoint]]" }
}
# reset release: recovery/removal checks into every clock
foreach dly {max min} {
 set ps [find_timing_paths -path_delay $dly -group_path_count 5 -endpoint_path_count 1 -sort_by_slack -to [get_pins -hierarchical */RN]]
 foreach p $ps { puts "PT_RN $dly [format %.3f [get_property $p slack]] [get_name [get_property $p endpoint_clock]] [get_full_name [get_property $p startpoint]] -> [get_full_name [get_property $p endpoint]]" }
}
