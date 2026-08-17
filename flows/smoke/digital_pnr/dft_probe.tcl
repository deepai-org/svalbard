read_liberty /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_5v00.lib
read_db $::env(DFT_INPUT_ODB)
read_sdc $::env(DFT_INPUT_SDC)
scan_replace
set_dft_config -max_chains 1
report_dft_config
report_dft_plan -verbose
execute_dft_plan
write_verilog $::env(DFT_NETLIST)
exit
