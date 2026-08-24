# SPDX-License-Identifier: Apache-2.0
# Select the drop-in StrongARM/SR-latch geometry from the shared layout engine.
set ::env(CML_TO_CMOS_FAST_LAYOUT) 1
set ::env(LAYOUT_ROUTE_DEBUG) 1
if {[catch {source /src/cml_to_cmos/layout.tcl} message options]} {
    puts stderr $message
    puts stderr [dict get $options -errorinfo]
    error $message
}
