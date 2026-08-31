# SPDX-License-Identifier: Apache-2.0
# Differential eight-finger NMOS sampling-switch baseline.
#
# This manually routed array reuses the verified GF180 finger/contact pattern
# from the Wi-Fi switching mixer.  Unlike the mixer, the two lower diffusion
# buses remain separate inputs and the upper buses are separate held outputs.

proc rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}
proc via_at {layer x y} {
    rect $layer [expr {$x-0.18}] [expr {$y-0.18}] \
        [expr {$x+0.18}] [expr {$y+0.18}]
}
proc stack23 {x y} {
    rect metal2 [expr {$x-0.28}] [expr {$y-0.28}] \
        [expr {$x+0.28}] [expr {$y+0.28}]
    rect metal3 [expr {$x-0.28}] [expr {$y-0.28}] \
        [expr {$x+0.28}] [expr {$y+0.28}]
    via_at via2 $x $y
}
proc stack34 {x y} {
    rect metal3 [expr {$x-0.28}] [expr {$y-0.28}] \
        [expr {$x+0.28}] [expr {$y+0.28}]
    rect metal4 [expr {$x-0.28}] [expr {$y-0.28}] \
        [expr {$x+0.28}] [expr {$y+0.28}]
    via_at via3 $x $y
}
proc port_at {name number x y} {
    rect metal4 [expr {$x-0.48}] [expr {$y-0.48}] \
        [expr {$x+0.48}] [expr {$y+0.48}]
    box values [expr {$x-0.48}] [expr {$y-0.48}] \
        [expr {$x+0.48}] [expr {$y+0.48}]
    label $name FreeSans 0.5 0 0 0 c metal4
    port make $number
}
proc ground_tap {x y} {
    # Each active array gets a local p-well contact and a wide M1--M4 stack.
    # Sampling-switch body modulation is a signal-path effect, so a single
    # remote substrate contact is not an acceptable baseline.
    rect psubdiff [expr {$x-0.55}] [expr {$y-0.55}] \
        [expr {$x+0.55}] [expr {$y+0.55}]
    rect psubdiffcont [expr {$x-0.25}] [expr {$y-0.30}] \
        [expr {$x+0.25}] [expr {$y+0.30}]
    foreach layer {metal1 metal2 metal3 metal4} {
        rect $layer [expr {$x-0.55}] [expr {$y-0.55}] \
            [expr {$x+0.55}] [expr {$y+0.55}]
    }
    foreach layer {via1 via2 via3} { via_at $layer $x $y }
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
        rect polysilicon [expr {$x-0.14}] [expr {$cy-$width/2.0-0.22}] \
            [expr {$x+0.14}] [expr {$cy+$width/2.0+0.22}]
    }
    foreach xoff [concat [diff_offsets $nf 0] [diff_offsets $nf 1]] {
        set x [expr {$cx+$xoff}]
        rect ndc [expr {$x-0.115}] [expr {$cy-$width/2.0+0.065}] \
            [expr {$x+0.115}] [expr {$cy+$width/2.0-0.065}]
        rect metal1 [expr {$x-0.18}] [expr {$cy-$width/2.0}] \
            [expr {$x+0.18}] [expr {$cy+$width/2.0}]
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
        rect polysilicon [expr {$x-0.20}] [expr {$gate_y-0.30}] \
            [expr {$x+0.20}] [expr {$gate_y+0.60}]
        rect polycontact [expr {$x-0.115}] [expr {$gate_y-0.215}] \
            [expr {$x+0.115}] [expr {$gate_y+0.015}]
    }
    rect metal1 [expr {$left+0.20}] [expr {$gate_y-0.30}] \
        [expr {$right-0.20}] [expr {$gate_y+0.30}]
    via_at via1 $cx $gate_y
}

crashbackups stop
load wifi_if_nmos_sample_switch
units microns
rect pwell 2 2 78 38
make_bank 25.0
make_bank 55.0

# Upper drain rails are the two held nodes, and go directly to matching M4
# exits.  No shared high-impedance sampled metal is hidden in a common bus.
rect metal2 21.42 20.82 28.58 21.58
stack23 28.0 21.20
rect metal3 27.72 21.20 28.28 31.0
stack34 28.0 31.0
port_at HOLDP 3 28.0 31.0
rect metal2 51.42 20.82 58.58 21.58
stack23 52.0 21.20
rect metal3 51.72 21.20 52.28 31.0
stack34 52.0 31.0
port_at HOLDN 4 52.0 31.0

# Lower source rails are the distinct differential IF inputs.  Their access
# geometry mirrors the held paths, while using independent M3 columns.
rect metal2 21.42 18.42 28.58 19.18
stack23 22.0 18.80
rect metal3 21.72 8.0 22.28 18.80
stack34 22.0 8.0
port_at INP 1 22.0 8.0
rect metal2 51.42 18.42 58.58 19.18
stack23 58.0 18.80
rect metal3 57.72 8.0 58.28 18.80
stack34 58.0 8.0
port_at INN 2 58.0 8.0

# One symmetric M2 clock spine fans into the two distributed gate contacts.
foreach x {25.0 55.0} {
    # Extend above the PCell's M1 gate bar so the Via1 enclosure remains legal.
    rect metal2 [expr {$x-0.28}] 13.72 [expr {$x+0.28}] 17.60
}
rect metal2 24.72 13.72 55.28 14.28
stack23 40.0 14.0
rect metal3 39.72 5.0 40.28 14.0
stack34 40.0 5.0
port_at CLK 5 40.0 5.0

# Contacted substrate return.  VSS remains explicit because eventual sampler
# noise and clock return currents must not be an implicit simulator ground.
# The two local contacts shorten each switching bank's body path; their M4
# spine stays above the held-node exits without contacting them.
ground_tap 25.0 27.5
ground_tap 55.0 27.5
foreach x {25.0 55.0} {
    rect metal4 [expr {$x-0.38}] 27.5 [expr {$x+0.38}] 33.5
}
rect metal4 4.25 33.22 55.0 33.78
rect metal4 4.25 27.5 4.81 33.5
stack34 4.25 27.5
port_at VSS 6 4.25 33.5

save /work/wifi_if_nmos_sample_switch
gds write /work/wifi_if_nmos_sample_switch.gds
quit -noprompt
