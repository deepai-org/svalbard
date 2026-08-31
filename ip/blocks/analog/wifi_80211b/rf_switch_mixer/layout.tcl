# SPDX-License-Identifier: Apache-2.0
# Two 8-finger NFET banks for the external-LO differential switching mixer.
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
proc port_at {name number x y} {
    rect metal4 [expr {$x-0.48}] [expr {$y-0.48}] [expr {$x+0.48}] [expr {$y+0.48}]
    box values [expr {$x-0.48}] [expr {$y-0.48}] [expr {$x+0.48}] [expr {$y+0.48}]
    label $name FreeSans 0.5 0 0 0 c metal4
    port make $number
}
proc gate_offsets {nf} {
    set result {}
    for {set index 0} {$index < $nf} {incr index} {
        lappend result [expr {-0.4*($nf-1)+0.8*$index}]
    }
    return $result
}
proc diff_offsets {nf parity} {
    set result {}
    set index 0
    for {set x [expr {-0.4*$nf}]} {$index <= $nf} {set x [expr {$x+0.8}]; incr index} {
        if {$index % 2 == $parity} { lappend result $x }
    }
    return $result
}
proc make_bank {cx} {
    set cy 20.0
    set width 4.0
    set nf 8
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
    foreach xoff [diff_offsets $nf 0] {
        set x [expr {$cx+$xoff}]
        rect metal1 [expr {$x-0.28}] 19.72 [expr {$x+0.28}] 21.48
        via_at via1 $x 21.20
    }
    foreach xoff [diff_offsets $nf 1] {
        set x [expr {$cx+$xoff}]
        rect metal1 [expr {$x-0.28}] 18.52 [expr {$x+0.28}] 20.28
        via_at via1 $x 18.80
    }
    set gate_y 17.25
    foreach xoff [gate_offsets $nf] {
        set x [expr {$cx+$xoff}]
        rect polysilicon [expr {$x-0.20}] [expr {$gate_y-0.30}] [expr {$x+0.20}] [expr {$gate_y+0.60}]
        rect polycontact [expr {$x-0.115}] [expr {$gate_y-0.215}] [expr {$x+0.115}] [expr {$gate_y+0.015}]
    }
    rect metal1 [expr {$left+0.20}] [expr {$gate_y-0.30}] [expr {$right-0.20}] [expr {$gate_y+0.30}]
    via_at via1 $cx $gate_y
}

crashbackups stop
load wifi_rf_switch_mixer
units microns
rect pwell 2 2 78 38

make_bank 25.0
make_bank 55.0

# IF drain rails use separate high-metal exits. RF source diffusion rails join
# only on metal2; LO and LOB have mirrored, separate gate exits.
rect metal2 21.42 20.82 28.58 21.58
stack23 28.0 21.20
rect metal3 27.72 21.20 28.28 31.0
stack34 28.0 31.0
port_at IFP 4 28.0 31.0
rect metal2 51.42 20.82 58.58 21.58
stack23 52.0 21.20
rect metal3 51.72 21.20 52.28 31.0
stack34 52.0 31.0
port_at IFN 5 52.0 31.0

rect metal2 21.42 18.42 58.58 19.18
stack23 40.0 18.80
rect metal3 39.72 6.0 40.28 18.80
stack34 40.0 6.0
port_at RF_IN 1 40.0 6.0

rect metal2 21.42 16.87 28.58 17.63
stack23 22.0 17.25
rect metal3 21.72 9.0 22.28 17.25
stack34 22.0 9.0
port_at LO 2 22.0 9.0
rect metal2 51.42 16.87 58.58 17.63
stack23 58.0 17.25
rect metal3 57.72 9.0 58.28 17.25
stack34 58.0 9.0
port_at LOB 3 58.0 9.0

rect psubdiff 3.93 27.93 4.57 28.67
rect psubdiffcont 4.00 28.00 4.50 28.60
rect metal1 3.55 27.55 4.95 29.05
via_at via1 4.25 28.3
rect metal2 3.87 27.92 4.63 28.68
stack23 4.25 28.3
rect metal3 3.97 28.3 4.53 33.0
stack34 4.25 33.0
port_at VSS 6 4.25 33.0

save /work/wifi_rf_switch_mixer
gds write /work/wifi_rf_switch_mixer.gds
quit -noprompt
