# Replacement for LibreLane's scripts/openroad/repair_design.tcl (bind-mounted by run_digital_hardening.sh).
# The flow runs OpenROAD.RepairDesignPostGPL twice (config.json meta.substituting_steps):
#   1st, BEFORE the final global placement: fanout (gain) buffering only, `repair_design -pre_placement
#        -buffer_gain`. Gain trees are built without regard to cell location, so they must be in the netlist
#        when the placer runs; built after placement (the stock order) their branches criss-cross the macro
#        (5.0 m of 8.1 m half-perimeter wire sat in such trees, and global routing did not converge even at 63 %).
#   2nd, after the final global placement: port buffers, location-aware slew / capacitance / wire repair
#        (no gain pass), tie cells, legalization = the stock step.
# The pass is chosen from the step's input: a database written by a global placement step means the second pass.
# The FIRM host-link launch / capture flops (config RSZ_DONT_TOUCH_LIST entries ending .lr / .lf) are dont-touch
# instances in the timing-repair steps only (an upsized one overlaps its neighbour or a tap: DPL-0033); here they
# are taken out of the list, because repair_design refuses to buffer a net that loads a dont-touch instance.
source $::env(SCRIPTS_DIR)/openroad/common/io.tcl
source $::env(SCRIPTS_DIR)/openroad/common/resizer.tcl

read_current_odb
unset_propagated_clock [all_clocks]
if { [info exists ::env(RSZ_DONT_TOUCH_LIST)] } {
    set pt_keep {}
    foreach o $::env(RSZ_DONT_TOUCH_LIST) { if { ![regexp {\.(lr|lf)$} $o] } { lappend pt_keep $o } }
    set ::env(RSZ_DONT_TOUCH_LIST) $pt_keep
}
set_dont_touch_objects
source $::env(SCRIPTS_DIR)/openroad/common/set_rc.tcl

set pt_gain 0
if { [info exists ::env(DESIGN_REPAIR_BUFFER_GAIN)] } { set pt_gain $::env(DESIGN_REPAIR_BUFFER_GAIN) }
set pt_two_pass [expr {[info exists ::env(PT_GAIN_BEFORE_GPL)] && $::env(PT_GAIN_BEFORE_GPL)}]
set pt_after_gpl [string match "*-openroad-globalplacement/*" $::env(CURRENT_ODB)]
set pt_first [expr {$pt_two_pass && !$pt_after_gpl}]
if { $pt_two_pass && $pt_gain <= 0 } { error "pt: PT_GAIN_BEFORE_GPL needs DESIGN_REPAIR_BUFFER_GAIN > 0" }
if { !$pt_two_pass && !$pt_after_gpl } { error "pt: repair_design before global placement without PT_GAIN_BEFORE_GPL (remove meta.substituting_steps)" }
puts "\[INFO\] pt: repair_design pass [expr {$pt_first ? 1 : 2}] (input $::env(CURRENT_ODB))"
if { $pt_first } {
    # no parasitics here: -pre_placement refuses to run on estimated ones (EST-0104)
    puts "\[INFO\] pt: pre-placement gain buffering pass (gain $pt_gain)"
    log_cmd repair_design -verbose -pre_placement -buffer_gain $pt_gain
    unset_dont_touch_objects
    write_views
    report_design_area_metrics
} else {
    estimate_parasitics -placement
    if { $::env(DESIGN_REPAIR_REMOVE_BUFFERS) } { remove_buffers }
    if { $::env(DESIGN_REPAIR_BUFFER_INPUT_PORTS) } {
        buffer_ports -inputs -buffer_cell [lindex [split $::env(SYNTH_BUFFER_CELL) "/"] 0]
    }
    if { $::env(DESIGN_REPAIR_BUFFER_OUTPUT_PORTS) } {
        buffer_ports -outputs -buffer_cell [lindex [split $::env(SYNTH_BUFFER_CELL) "/"] 0]
    }
    set arg_list [list -verbose]
    lappend arg_list -max_wire_length $::env(DESIGN_REPAIR_MAX_WIRE_LENGTH)
    lappend arg_list -slew_margin $::env(DESIGN_REPAIR_MAX_SLEW_PCT)
    lappend arg_list -cap_margin $::env(DESIGN_REPAIR_MAX_CAP_PCT)
    if { [info exists ::env(DESIGN_REPAIR_MAX_UTILIZATION)] } {
        lappend arg_list -max_utilization $::env(DESIGN_REPAIR_MAX_UTILIZATION)
    }
    if { !$pt_two_pass && $pt_gain > 0 } { lappend arg_list -buffer_gain $pt_gain }
    log_cmd repair_design {*}$arg_list
    if { $::env(DESIGN_REPAIR_TIE_FANOUT) } {
        repair_tie_fanout -verbose -separation $::env(DESIGN_REPAIR_TIE_SEPARATION) $::env(SYNTH_TIELO_CELL)
        repair_tie_fanout -verbose -separation $::env(DESIGN_REPAIR_TIE_SEPARATION) $::env(SYNTH_TIEHI_CELL)
    }
    report_floating_nets -verbose
    source $::env(SCRIPTS_DIR)/openroad/common/dpl.tcl
    unset_dont_touch_objects
    source $::env(SCRIPTS_DIR)/openroad/common/set_rc.tcl
    estimate_parasitics -placement
    write_views
}
