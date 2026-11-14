read_liberty /src/verification/digital_hardening/liberty/gf180mcu_fd_sc_mcu7t5v0__ss_032C_3v15.lib
read_verilog $::env(NL)
link_design pt_digital_macro
source /src/integration/pt_digital_macro.sdc
puts "SDC-OK keys [llength $pt_por_keys] ag [llength $pt_ag]"
puts "WNS [sta::worst_slack_cmd max]"
