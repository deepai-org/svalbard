# SPDX-License-Identifier: Apache-2.0
# Die-side RF characterization replica of the Wi-Fi 16-finger LNA NFET array.
# GATE, DRAIN, SOURCE, and VSS are distinct electrical ports.  The M5 landings
# and adjacent grounds support a future G-S-G probe/pad implementation but are
# intentionally not represented as qualified production pad cells.

proc dc_rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}
proc dc_via {layer x y} {
    dc_rect $layer [expr {$x-0.28}] [expr {$y-0.28}] \
        [expr {$x+0.28}] [expr {$y+0.28}]
}
proc dc_device_via1 {x y} {
    # The dense finger contacts use the LNA-proven Via1 enclosure; the larger
    # stacks above use dc_via because their enclosing metals are wider.
    dc_rect via1 [expr {$x-0.18}] [expr {$y-0.18}] \
        [expr {$x+0.18}] [expr {$y+0.18}]
}
proc dc_stack15 {x y} {
    foreach layer {metal1 metal2 metal3 metal4 metal5} {
        dc_rect $layer [expr {$x-0.55}] [expr {$y-0.55}] \
            [expr {$x+0.55}] [expr {$y+0.55}]
    }
    foreach layer {via1 via2 via3 via4} { dc_via $layer $x $y }
}
proc dc_stack25 {x y} {
    # Device buses already reach Metal2 through dense, LNA-proven Via1 sites.
    # Starting this larger landing stack at Metal2 avoids disturbing those
    # finger-scale contacts while retaining the full route in extracted PEX.
    foreach layer {metal2 metal3 metal4 metal5} {
        dc_rect $layer [expr {$x-0.55}] [expr {$y-0.55}] \
            [expr {$x+0.55}] [expr {$y+0.55}]
    }
    foreach layer {via2 via3 via4} { dc_via $layer $x $y }
}
proc dc_stack45 {x y} {
    foreach layer {metal4 metal5} {
        dc_rect $layer [expr {$x-0.55}] [expr {$y-0.55}] \
            [expr {$x+0.55}] [expr {$y+0.55}]
    }
    dc_via via4 $x $y
}
proc dc_port {name number x y} {
    dc_rect metal5 [expr {$x-7.0}] [expr {$y-7.0}] \
        [expr {$x+7.0}] [expr {$y+7.0}]
    box values [expr {$x-7.0}] [expr {$y-7.0}] \
        [expr {$x+7.0}] [expr {$y+7.0}]
    label $name FreeSans 1.0 0 0 0 c metal5
    port make $number
}
proc dc_gsg_grounds {x y} {
    # Ground strips share the local M4 reference plane. Their dimensions are
    # deliberately inspectable die-side geometry, not a pad qualification.
    foreach dx {-18.0 18.0} {
        set gx [expr {$x+$dx}]
        dc_rect metal5 [expr {$gx-3.5}] [expr {$y-7.0}] \
            [expr {$gx+3.5}] [expr {$y+7.0}]
        dc_stack45 $gx [expr {$y-5.5}]
        dc_rect metal4 [expr {$gx-0.55}] 18.0 [expr {$gx+0.55}] \
            [expr {$y-5.5}]
    }
}
proc dc_gate_offsets {nf} {
    set result {}
    for {set index 0} {$index < $nf} {incr index} {
        lappend result [expr {-0.4*($nf-1)+0.8*$index}]
    }
    return $result
}
proc dc_diff_offsets {nf parity} {
    set result {}
    set index 0
    for {set x [expr {-0.4*$nf}]} {$index <= $nf} {set x [expr {$x+0.8}]; incr index} {
        if {$index % 2 == $parity} { lappend result $x }
    }
    return $result
}

crashbackups stop
load wifi_rf_nfet_array_coupon
units microns

# The device array uses the same finger width, length, pitch and terminal
# ordering as the active LNA core; only the long measurement access routes are
# different and are kept outside the compact central active region.
set cx 160.0
set cy 112.0
set width 4.0
set nf 16
set left [expr {$cx-0.4*$nf-0.18}]
set right [expr {$cx+0.4*$nf+0.18}]
dc_rect pwell 4 4 316 216
dc_rect ndiff $left [expr {$cy-$width/2.0}] $right [expr {$cy+$width/2.0}]
foreach xoff [dc_gate_offsets $nf] {
    set x [expr {$cx+$xoff}]
    dc_rect polysilicon [expr {$x-0.14}] [expr {$cy-$width/2.0-0.22}] \
        [expr {$x+0.14}] [expr {$cy+$width/2.0+0.22}]
}
foreach xoff [concat [dc_diff_offsets $nf 0] [dc_diff_offsets $nf 1]] {
    set x [expr {$cx+$xoff}]
    dc_rect ndc [expr {$x-0.115}] [expr {$cy-$width/2.0+0.065}] \
        [expr {$x+0.115}] [expr {$cy+$width/2.0-0.065}]
    dc_rect metal1 [expr {$x-0.18}] [expr {$cy-$width/2.0}] \
        [expr {$x+0.18}] [expr {$cy+$width/2.0}]
}

# DRAIN and SOURCE use separate, compact metal-2 buses.  Both make direct
# M1-to-M5 transitions before their measurement routes, preserving access-RC
# in PEX while avoiding a hidden ideal common-source connection.
set drain_y [expr {$cy+1.20}]
set source_y [expr {$cy-1.20}]
set drain_xs {}
foreach xoff [dc_diff_offsets $nf 0] { lappend drain_xs [expr {$cx+$xoff}] }
set source_xs {}
foreach xoff [dc_diff_offsets $nf 1] { lappend source_xs [expr {$cx+$xoff}] }
foreach x $drain_xs {
    dc_rect metal1 [expr {$x-0.28}] [expr {$cy-0.28}] \
        [expr {$x+0.28}] [expr {$drain_y+0.28}]
    dc_device_via1 $x $drain_y
}
dc_rect metal2 [expr {[lindex $drain_xs 0]-0.38}] [expr {$drain_y-0.38}] \
    [expr {[lindex $drain_xs end]+0.38}] [expr {$drain_y+0.38}]
dc_stack25 165.0 $drain_y
dc_rect metal5 164.45 [expr {$drain_y-0.55}] 248.0 [expr {$drain_y+0.55}]
dc_rect metal5 247.45 $drain_y 248.55 178.0

foreach x $source_xs {
    dc_rect metal1 [expr {$x-0.28}] [expr {$source_y-0.28}] \
        [expr {$x+0.28}] [expr {$cy+0.28}]
    dc_device_via1 $x $source_y
}
dc_rect metal2 [expr {[lindex $source_xs 0]-0.38}] [expr {$source_y-0.38}] \
    [expr {[lindex $source_xs end]+0.38}] [expr {$source_y+0.38}]
dc_stack25 155.0 $source_y
dc_rect metal5 154.45 48.0 155.55 $source_y
dc_rect metal5 155.0 47.45 160.0 48.55

# Gate contacts remain distributed across all fingers.  Their M1 rail joins a
# single high-metal landing so gate resistance is retained by extraction.
set gate_y [expr {$cy-2.75}]
foreach xoff [dc_gate_offsets $nf] {
    set x [expr {$cx+$xoff}]
    dc_rect polysilicon [expr {$x-0.20}] [expr {$gate_y-0.30}] \
        [expr {$x+0.20}] [expr {$gate_y+0.60}]
    dc_rect polycontact [expr {$x-0.115}] [expr {$gate_y-0.215}] \
        [expr {$x+0.115}] [expr {$gate_y+0.015}]
}
dc_rect metal1 [expr {[lindex $drain_xs 0]+0.05}] [expr {$gate_y-0.30}] \
    [expr {[lindex $drain_xs end]-0.05}] [expr {$gate_y+0.30}]
dc_device_via1 160.0 $gate_y
dc_stack25 160.0 $gate_y
dc_rect metal5 159.45 $gate_y 160.55 178.0

# A contacted substrate ring and common M4 plane give the body a real return.
# VSS stays a distinct electrical port so measurement fixtures can record the
# return-path impedance instead of silently treating the substrate as ideal.
dc_rect metal4 8 18 312 21
dc_rect psubdiff 4 4 316 4.8
dc_rect psubdiff 4 215.2 316 216
dc_rect psubdiff 4 4 4.8 216
dc_rect psubdiff 315.2 4 316 216
dc_rect metal1 4 4 316 4.8
dc_rect metal1 4 215.2 316 216
dc_rect metal1 4 4 4.8 216
dc_rect metal1 315.2 4 316 216
foreach x {8 24 40 56 72 88 104 120 136 152 168 184 200 216 232 248 264 280 296 312} {
    dc_rect psubdiffcont [expr {$x-0.25}] 4.15 [expr {$x+0.25}] 4.65
    dc_rect psubdiffcont [expr {$x-0.25}] 215.35 [expr {$x+0.25}] 215.85
}
foreach y {20 36 52 68 84 100 116 132 148 164 180 196} {
    dc_rect psubdiffcont 4.15 [expr {$y-0.25}] 4.65 [expr {$y+0.25}]
    dc_rect psubdiffcont 315.35 [expr {$y-0.25}] 315.85 [expr {$y+0.25}]
}
# The perimeter contact ring reaches this vertical M1--M4 spine.  Individual
# Via1--Via3 cuts deliberately sit away from the dense active device region.
foreach layer {metal1 metal2 metal3 metal4} {
    dc_rect $layer 47.45 4.0 48.55 20.0
}
foreach layer {via1 via2 via3} { dc_via $layer 48.0 10.0 }
dc_stack45 48.0 20.0
dc_rect metal5 47.45 20.0 48.55 178.0

# Comparable M5 signal landings and local ground strips define the dielectric
# environment which later wafer work must characterize.
dc_port GATE 1 160.0 178.0
dc_gsg_grounds 160.0 178.0
dc_port DRAIN 2 248.0 178.0
dc_gsg_grounds 248.0 178.0
dc_port SOURCE 3 160.0 48.0
dc_gsg_grounds 160.0 48.0
dc_port VSS 4 48.0 178.0

save /work/wifi_rf_nfet_array_coupon
gds write /work/wifi_rf_nfet_array_coupon.gds
quit -noprompt
