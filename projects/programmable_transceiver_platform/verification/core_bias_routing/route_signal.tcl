# Signal routing around the FIXED supply network.
read_db /work/signal-placed.odb
source /work/supply-sboxes.tcl
set_thread_count [expr {[info exists ::env(ROUTE_THREADS)] ? $::env(ROUTE_THREADS) : 4}]
source /flow/tracks.tcl
set_routing_layers -signal Metal2-Metal5
set_global_routing_layer_adjustment Metal2-Metal5 0.0
global_route -guide_file /work/signal.guide -verbose
detailed_route -output_drc /work/signal-route.drc -verbose 1 -droute_end_iter 40
write_db /work/routed.odb
write_def /work/routed.def
exit
