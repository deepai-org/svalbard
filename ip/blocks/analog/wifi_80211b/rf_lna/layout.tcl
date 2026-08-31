# SPDX-License-Identifier: Apache-2.0
# Four-terminal, 16-finger NFET LNA core. Matching/bias/load are external.
proc rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}
proc via_at {layer x y} {
    rect $layer [expr {$x-0.18}] [expr {$y-0.18}] [expr {$x+0.18}] [expr {$y+0.18}]
}
proc stack23 {x y} {
    rect metal2 [expr {$x-0.28}] [expr {$y-0.28}] [expr {$x+0.28}] [expr {$y+0.28}]
    rect metal3 [expr {$x-0.28}] [expr {$y-0.28}] [expr {$x+0.28}] [expr {$y+0.28}]
    via_at via2 $x $y
}
proc stack34 {x y} {
    rect metal3 [expr {$x-0.28}] [expr {$y-0.28}] [expr {$x+0.28}] [expr {$y+0.28}]
    rect metal4 [expr {$x-0.28}] [expr {$y-0.28}] [expr {$x+0.28}] [expr {$y+0.28}]
    via_at via3 $x $y
}
proc diff_offsets {nf parity} {
    set result {}
    set index 0
    for {set x [expr {-0.4*$nf}]} {$index <= $nf} {set x [expr {$x+0.8}]; incr index} {
        if {$index % 2 == $parity} { lappend result $x }
    }
    return $result
}
proc gate_offsets {nf} {
    set result {}
    for {set index 0} {$index < $nf} {incr index} {
        lappend result [expr {-0.4*($nf-1)+0.8*$index}]
    }
    return $result
}
proc make_port {name number x y} {
    rect metal4 [expr {$x-0.48}] [expr {$y-0.48}] [expr {$x+0.48}] [expr {$y+0.48}]
    box values [expr {$x-0.48}] [expr {$y-0.48}] [expr {$x+0.48}] [expr {$y+0.48}]
    label $name FreeSans 0.5 0 0 0 c metal4
    port make $number
}

crashbackups stop
load wifi_lna_cs_core
units microns
rect pwell 2 2 38 38

set cx 20.0
set cy 20.0
set width 4.0
set nf 16
set left [expr {$cx-0.4*$nf-0.18}]
set right [expr {$cx+0.4*$nf+0.18}]
rect ndiff $left [expr {$cy-$width/2.0}] $right [expr {$cy+$width/2.0}]
foreach xoff [gate_offsets $nf] {
    set x [expr {$cx+$xoff}]
    rect polysilicon [expr {$x-0.14}] [expr {$cy-$width/2.0-0.22}] [expr {$x+0.14}] [expr {$cy+$width/2.0+0.22}]
}
foreach xoff [concat [diff_offsets $nf 0] [diff_offsets $nf 1]] {
    set x [expr {$cx+$xoff}]
    rect ndc [expr {$x-0.115}] [expr {$cy-$width/2.0+0.065}] [expr {$x+0.115}] [expr {$cy+$width/2.0-0.065}]
    rect metal1 [expr {$x-0.18}] [expr {$cy-$width/2.0}] [expr {$x+0.18}] [expr {$cy+$width/2.0}]
}

# Alternate diffusion columns are tied as RF_OUT and RF_SOURCE. Gate fingers
# share one compact poly contact rail. The body has an explicit nearby VSS tap.
set drain_y 21.20
set source_y 18.80
set drain_xs {}
foreach xoff [diff_offsets $nf 0] { lappend drain_xs [expr {$cx+$xoff}] }
set source_xs {}
foreach xoff [diff_offsets $nf 1] { lappend source_xs [expr {$cx+$xoff}] }
foreach x $drain_xs {
    rect metal1 [expr {$x-0.28}] 19.72 [expr {$x+0.28}] [expr {$drain_y+0.28}]
    via_at via1 $x $drain_y
}
rect metal2 [expr {[lindex $drain_xs 0]-0.38}] [expr {$drain_y-0.38}] [expr {[lindex $drain_xs end]+0.38}] [expr {$drain_y+0.38}]
stack23 26.4 $drain_y
rect metal3 26.12 $drain_y 26.68 31.0
stack34 26.4 31.0
make_port RF_OUT 2 26.4 31.0
foreach x $source_xs {
    rect metal1 [expr {$x-0.28}] [expr {$source_y-0.28}] [expr {$x+0.28}] 20.28
    via_at via1 $x $source_y
}
rect metal2 [expr {[lindex $source_xs 0]-0.38}] [expr {$source_y-0.38}] [expr {[lindex $source_xs end]+0.38}] [expr {$source_y+0.38}]
stack23 20.0 $source_y
rect metal3 19.72 6.0 20.28 $source_y
stack34 20.0 6.0
make_port RF_SOURCE 3 20.0 6.0

set gate_y 17.25
foreach xoff [gate_offsets $nf] {
    set x [expr {$cx+$xoff}]
    rect polysilicon [expr {$x-0.20}] [expr {$gate_y+0.35}] [expr {$x+0.20}] [expr {$gate_y+0.60}]
    rect polysilicon [expr {$x-0.20}] [expr {$gate_y-0.30}] [expr {$x+0.20}] [expr {$gate_y+0.60}]
    rect polycontact [expr {$x-0.115}] [expr {$gate_y-0.215}] [expr {$x+0.115}] [expr {$gate_y+0.015}]
}
rect metal1 [expr {[lindex $drain_xs 0]+0.05}] [expr {$gate_y-0.30}] [expr {[lindex $drain_xs end]-0.05}] [expr {$gate_y+0.30}]
via_at via1 16.0 $gate_y
stack23 16.0 $gate_y
rect metal3 15.72 9.0 16.28 $gate_y
stack34 16.0 9.0
make_port RF_IN 1 16.0 9.0

rect psubdiff 3.93 27.93 4.57 28.67
rect psubdiffcont 4.00 28.00 4.50 28.60
rect metal1 3.55 27.55 4.95 29.05
via_at via1 4.25 28.3
rect metal2 3.87 27.92 4.63 28.68
stack23 4.25 28.3
rect metal3 3.97 28.3 4.53 33.0
stack34 4.25 33.0
make_port VSS 4 4.25 33.0

save /work/wifi_lna_cs_core
gds write /work/wifi_lna_cs_core.gds
quit -noprompt
