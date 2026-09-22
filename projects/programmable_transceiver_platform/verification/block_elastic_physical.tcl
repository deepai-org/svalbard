# Digital-region placement experiment only: no pads, analog macros, PDN or CTS.
set base /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0
read_lef $base/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef
read_lef $base/lef/gf180mcu_fd_sc_mcu7t5v0.lef
read_liberty $base/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib
read_verilog /mapped/mapped.v
link_design pt_block_elastic
# A local 500 x 400 um digital region, not the whole chip's floorplan.
initialize_floorplan -site GF018hv5v_mcu_sc7 -die_area {0 0 520 420} -core_area {10 10 510 410}
make_tracks
place_pins -hor_layers Metal3 -ver_layers Metal4
# No timing repair here: isolate placement feasibility of the verified netlist.
global_placement -density 0.55
detailed_placement
check_placement -verbose
report_design_area
write_db /out/placed.odb
write_def /out/digital.def
set block [ord::get_db_block]
set dbu [$block getDbUnitsPerMicron]
set count 0
set area 0.0
set unplaced 0
set geometry [open /out/cells.tsv w]
foreach inst [$block getInsts] {
 set box [$inst getBBox]
 puts $geometry "[$inst getName]\t[$box xMin]\t[$box yMin]\t[$box xMax]\t[$box yMax]\t[$inst getOrient]"
 incr count
 set master [$inst getMaster]
 set area [expr {$area + double([$master getWidth])*[$master getHeight]/$dbu/$dbu}]
 if {![$inst isPlaced]} {incr unplaced}
}
close $geometry
set file [open /out/placement-counts.json w]
puts $file "{\"instances\": $count, \"cell_area_um2\": $area, \"unplaced\": $unplaced, \"requested_region_um2\": 200000}"
close $file
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

