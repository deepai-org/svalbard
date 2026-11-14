read_lef /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/techlef/gf180mcu_fd_sc_mcu7t5v0__max.tlef
read_lef /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lef/gf180mcu_fd_sc_mcu7t5v0.lef
read_liberty /src/verification/digital_hardening/liberty/gf180mcu_fd_sc_mcu7t5v0__ss_032C_3v15.lib
read_verilog $::env(NL)
link_design pt_digital_macro
set PT_TIMING_CORNER ss_window
set PT_LIB_CHARACTERIZED 1
set HOST_RATE_DIV 1
source /src/integration/pt_digital_macro.sdc
set_load 0.02 [all_outputs]
repair_design -pre_placement -buffer_gain 4.0
proc short {n} { regsub -all {_gf180mcu_fd_sc_mcu7t5v0__[A-Za-z0-9_]*} $n {} n; regsub -all {\[[0-9]+\]} $n {[]} n; return $n }
foreach p [find_timing_paths -path_delay max -group_path_count 4000 -endpoint_path_count 1 -unique_paths_to_endpoint -sort_by_slack -slack_max $::env(SMAX)] {
  set s [get_property $p slack]
  set sc [get_property $p startpoint_clock]; set ec [get_property $p endpoint_clock]
  puts "P [format %.2f $s] [expr {$sc eq "" ? "-" : [get_name $sc]}] [expr {$ec eq "" ? "-" : [get_name $ec]}] [short [get_full_name [get_property $p startpoint]]] [short [get_full_name [get_property $p endpoint]]] [llength [get_property $p points]]"
}
