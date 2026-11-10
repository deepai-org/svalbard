# Supply-first routing: only the seven supply nets have instance terminals.
read_db /work/power-placed.odb
set_thread_count [expr {[info exists ::env(ROUTE_THREADS)] ? $::env(ROUTE_THREADS) : 4}]
source /flow/tracks.tcl
set_routing_layers -signal Metal2-Metal5
set_global_routing_layer_adjustment Metal2-Metal5 0.0
global_route -guide_file /work/power.guide -verbose
detailed_route -output_drc /work/power-route.drc -verbose 1 -droute_end_iter 40
write_db /work/power-routed.odb
write_def /work/power-routed.def
exit
