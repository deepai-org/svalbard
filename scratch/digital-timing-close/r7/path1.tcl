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
foreach c $::env(CLKS) {
  puts "=== $c"
  report_checks -path_delay max -from [get_clocks $c] -to [get_clocks $c] -group_path_count 1 -fields {fanout cap slew} -digits 2
}
