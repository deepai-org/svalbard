# Digital-region placement experiment only: no pads, analog macros, PDN or CTS.
set base /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0
read_lef $base/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef
read_lef $base/lef/gf180mcu_fd_sc_mcu7t5v0.lef
read_liberty $base/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib
read_verilog /out/input.v
link_design pt_digital
# A local 1500 x 1530 um digital region, not the whole chip's floorplan.
initialize_floorplan -site GF018hv5v_mcu_sc7 -die_area {0 0 1520 1550} -core_area {10 10 1510 1540}
make_tracks
place_pins -hor_layers Metal3 -ver_layers Metal4
# No timing repair here: isolate placement feasibility of the verified netlist.
global_placement -density 0.55
detailed_placement
check_placement -verbose
report_design_area
write_db /out/digital.odb
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
puts $file "{\"instances\": $count, \"cell_area_um2\": $area, \"unplaced\": $unplaced, \"requested_region_um2\": 2295000}"
close $file
exit
