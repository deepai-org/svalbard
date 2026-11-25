# Stage `route` (tool image, OpenROAD):  tool.sh <chip> -c 4 openroad -exit /asm/route.tcl
# Top-level routing test: blocks, pads and the power grid as fixed hard macros (LEF abstracts from their GDS), every
# top-level net of the chip conn (nets.json) routed by FastRoute (global) and TritonRoute (detailed) on Metal2-Metal5.
# Net classes (place stage): supply (island rails, regulator outputs) 3 um wide, hook (block supply pin -> grid) 1.2 um;
# clock / hs / rf twice the minimum spacing (no shields: none of the specs asks for a drawn shield on a top-level net).
set tlef /pdk/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/techlef/gf180mcu_fd_sc_mcu7t5v0__nom.tlef
set thr [expr {[info exists ::env(THREADS)] ? $::env(THREADS) : 1}]
set_thread_count $thr
read_lef $tlef
foreach f [lsort [glob /run/lef/*.lef]] { read_lef $f }
read_def /run/design.def
make_tracks
set_routing_layers -signal Metal2-Metal5
# pins the router cannot reach (found by earlier pin-access passes, run.sh): taken off their nets and reported
set nun 0
if {[file exists /run/route/unreachable.txt]} {
  set fp [open /run/route/unreachable.txt r]
  foreach l [split [read $fp] "\n"] {
    if {$l == ""} { continue }
    set it [[ord::get_db_block] findITerm $l]
    if {$it != "NULL" && $it != ""} { $it disconnect; incr nun }
  }
  close $fp
}
puts "UNREACHABLE pins disconnected: $nun"
# NDRs are given to the detailed router (and its pin access) only: FastRoute stops with GRT-0228 (edge usage over its
# limit at the macro corner) when the wide classes are in the global route
proc assign_classes {} {
  global txt
  set nwide 0; set nspc 0
  set use_ndr [expr {[info exists ::env(NDR)] ? $::env(NDR) : 1}]
  foreach line [split $txt "\n"] {
    if {[regexp {^"([^"]+)": \{$} $line -> name]} { set cur $name }
    if {[regexp {"cls": "([a-z]+)"} $line -> cls]} {
      set net [get_nets -quiet $cur]
      if {$net == ""} { continue }
      if {$use_ndr && $cls == "supply"} { assign_ndr -ndr WIDE -net $cur; incr nwide }
      if {$use_ndr && $cls == "hook"} { assign_ndr -ndr HOOK -net $cur; incr nwide }
      if {$use_ndr && $cls == "lo"} { assign_ndr -ndr LOSH -net $cur; incr nspc }
      if {$use_ndr && [info exists ::env(SPC2)] && ($cls == "clock" || $cls == "hs" || $cls == "rf")} { assign_ndr -ndr SPC2 -net $cur; incr nspc }   ;# off by default: double spacing could not enter the pin windows (TXPH, WIRE_TX)
    }
  }
  puts "NDR WIDE/HOOK $nwide nets, SPC2 $nspc nets"
}
# net classes
set fp [open /run/nets.json r]; set txt [read $fp]; close $fp
create_ndr -name WIDE -width {Metal2 1.0 Metal3 1.0 Metal4 1.0 Metal5 1.0} -spacing {Metal2 0.6 Metal3 0.6 Metal4 0.6 Metal5 0.9}   ;# 3 um could not enter the switch VISL pins
set hw [expr {[info exists ::env(HOOK_W)] ? $::env(HOOK_W) : 1.2}]
create_ndr -name HOOK -width "Metal2 $hw Metal3 $hw Metal4 $hw Metal5 $hw" -spacing {Metal2 0.3 Metal3 0.3 Metal4 0.3 Metal5 0.6}
create_ndr -name LOSH -width {Metal2 0.56 Metal3 0.56 Metal4 0.56 Metal5 0.9} -spacing {Metal2 1.2 Metal3 1.2 Metal4 1.2 Metal5 1.2}
create_ndr -name SPC2 -spacing {Metal2 0.56 Metal3 0.56 Metal4 0.56 Metal5 0.92} -width {Metal2 0.28 Metal3 0.28 Metal4 0.28 Metal5 0.44}
set PA {-via_in_pin_bottom_layer Metal2 -via_in_pin_top_layer Metal5}
if {[info exists ::env(PA_ONLY)]} { assign_classes; pin_access {*}$PA -verbose 0; puts "PA CLEAN"; exit }
set_global_routing_layer_adjustment Metal2-Metal5 0.15
global_route -congestion_iterations 30 -congestion_report_file /run/route/congestion.rpt -allow_congestion -verbose
write_guides /run/route/route.guide
write_def /run/route/groute.def
if {[info exists ::env(GR_ONLY)]} { puts "GR ONLY"; exit }
# antenna: layer jumpers on the global routes of long top-level nets (no diode cells: the top has no rows)
if {[catch {repair_antennas -jumper_only -iterations 3} err]} { puts "ANTENNA REPAIR skipped: $err" }
assign_classes
set iters [expr {[info exists ::env(DRT_ITERS)] ? $::env(DRT_ITERS) : 64}]
detailed_route {*}$PA -output_drc /run/route/drt.rpt -output_maze /run/route/maze.log -droute_end_iter $iters -verbose 1 \
  -save_guide_updates
# antenna: a second jumper pass on the detailed routes (the global-route pass misses nets whose layer use changes in DRT)
if {![info exists ::env(NO_ANT2)]} {
  if {[catch {repair_antennas -jumper_only -iterations 3} err]} { puts "ANTENNA REPAIR 2 skipped: $err" } else {
    detailed_route {*}$PA -output_drc /run/route/drt.rpt -droute_end_iter 16 -verbose 1
  }
}
write_def /run/route/routed.def
catch {check_antennas -report_file /run/route/antenna.rpt}
puts "ROUTE DONE"
