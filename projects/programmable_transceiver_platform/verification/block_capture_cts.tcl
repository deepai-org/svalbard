set base /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0
read_liberty $base/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib
read_db /placed/digital.odb
create_clock -name wr_clk -period 25.6 [get_ports wr_clk]
create_clock -name rd_clk -period 25.6 [get_ports rd_clk]
set_wire_rc -signal -layer Metal3
set_wire_rc -clock -layer Metal4
clock_tree_synthesis -buf_list {gf180mcu_fd_sc_mcu7t5v0__clkbuf_4 gf180mcu_fd_sc_mcu7t5v0__clkbuf_8} -root_buf gf180mcu_fd_sc_mcu7t5v0__clkbuf_8 -sink_clustering_enable -sink_clustering_size 20 -sink_clustering_max_diameter 100
 detailed_placement
check_placement -verbose
report_cts
write_db /out/digital.odb
write_def /out/digital.def
exit
