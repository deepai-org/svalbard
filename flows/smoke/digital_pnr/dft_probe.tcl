read_liberty /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_5v00.lib
read_db $::env(FINAL_DIR)/odb/counter.odb
scan_replace
set_dft_config -max_chains 1
scan_opt
write_verilog $::env(DFT_NETLIST)
exit
