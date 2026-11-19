# exp.tcl: buffering-order experiment on a post-GPL odb. env: EXP_ENV (step _env.tcl), EXP_ODB, EXP_VAR (A|B|C|D), EXP_OUT
set ::env(_TCL_ENV_IN) $::env(EXP_ENV)
set ::env(_LIB_CORNER_0) "max_ss_032C_3v15 /out/design/lib/gf180mcu_fd_sc_mcu7t5v0__ss_032C_3v15.lib"
if {[info exists ::env(EXP_CORNERS)]} { set i 1; foreach c $::env(EXP_CORNERS) { set ::env(_LIB_CORNER_$i) "min_$c /out/design/lib/gf180mcu_fd_sc_mcu7t5v0__$c.lib"; incr i } }
set ::env(_SDC_IN) /out/design/pt_digital_macro.sdc
set ::env(SCRIPTS_DIR) /usr/local/lib/python3.12/dist-packages/librelane/scripts
set var $::env(EXP_VAR); set out $::env(EXP_OUT)
source $::env(SCRIPTS_DIR)/openroad/common/io.tcl
source $::env(SCRIPTS_DIR)/openroad/common/resizer.tcl
set ::env(CURRENT_ODB) $::env(EXP_ODB)
set xc {}
foreach f [list $::env(PNR_EXCLUDED_CELL_FILE)] { set fh [open $f]; foreach l [split [read $fh] "\n"] { set l [string trim $l]; if {$l ne "" && [string index $l 0] ne "#"} {lappend xc $l} }; close $fh }
foreach c $::env(EXTRA_EXCLUDED_CELLS) { lappend xc $c }
set ::env(_PNR_EXCLUDED_CELLS) $xc
read_current_odb
unset_propagated_clock [all_clocks]
set_dont_touch_objects
source $::env(SCRIPTS_DIR)/openroad/common/set_rc.tcl
estimate_parasitics -placement
proc rd {gain} {
  set a [list -verbose -max_wire_length 0 -slew_margin 10 -cap_margin 10]
  if { $gain > 0 } { lappend a -buffer_gain $gain }
  repair_design {*}$a
}
proc gp {} {
  global_placement -density [expr $::env(PL_TARGET_DENSITY_PCT)/100.0] -pad_right [expr $::env(GPL_CELL_PADDING)/2] -pad_left [expr $::env(GPL_CELL_PADDING)/2] -init_wirelength_coef $::env(PL_WIRE_LENGTH_COEF) {*}$::gpx
}
foreach {k v} {PL_TARGET_DENSITY_PCT 68 PL_WIRE_LENGTH_COEF 0.25 GPL_CELL_PADDING 0} { if {![info exists ::env($k)]} { set ::env($k) $v } }
set ::gpx {}
if {[info exists ::env(EXP_GPX)]} { set ::gpx $::env(EXP_GPX) }
buffer_ports -inputs -buffer_cell [lindex [split $::env(SYNTH_BUFFER_CELL) "/"] 0]
buffer_ports -outputs -buffer_cell [lindex [split $::env(SYNTH_BUFFER_CELL) "/"] 0]
switch $var {
  A { rd 4.0 }
  B { rd 4.0; gp; estimate_parasitics -placement; rd 0 }
  C { rd 0 }
  D { gp; estimate_parasitics -placement; rd 0 }
}
source $::env(SCRIPTS_DIR)/openroad/common/dpl.tcl
unset_dont_touch_objects
estimate_parasitics -placement
write_def $out/$var.def
write_db $out/$var.odb
report_design_area
report_checks -path_delay max -group_path_count 1 > $out/$var.max.rpt
report_tns; report_wns
if {![info exists ::env(EXP_NOGRT)]} {
source $::env(SCRIPTS_DIR)/openroad/common/set_routing_layers.tcl
source $::env(SCRIPTS_DIR)/openroad/common/set_layer_adjustments.tcl
catch {global_route -congestion_iterations 3 -verbose -allow_congestion} e
puts $e
}
