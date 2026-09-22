# Compare routing demand with two PDNs; pre-CTS, no detailed routing/signoff.
read_liberty /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib
read_db /input/digital-pdn.odb
set_routing_layers -signal Metal2-Metal5 -clock Metal2-Metal5
# Keep congestion visible and write its report even when the grid cannot fit.
global_route -congestion_iterations 50 -allow_congestion -congestion_report_file /out/congestion.rpt -guide_file /out/routes.guide -verbose
puts "PDN_ROUTING_SCREEN_COMPLETE"
exit
