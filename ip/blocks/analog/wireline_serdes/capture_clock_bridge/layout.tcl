# SPDX-License-Identifier: Apache-2.0
# Local dual-phase WRITE-to-complementary-capture-clock bridge for GF180MCU.

proc rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}
proc via {layer x y} {
    rect $layer [expr {$x-0.18}] [expr {$y-0.18}] \
        [expr {$x+0.18}] [expr {$y+0.18}]
}
proc stack_to_m4 {x y} {
    # Keep more than the minimum enclosure around diffusion/poly contacts;
    # 0.60 um was quantized down at a few body-contact sites.
    rect metal1 [expr {$x-0.45}] [expr {$y-0.45}] [expr {$x+0.45}] [expr {$y+0.45}]
    rect metal2 [expr {$x-0.23}] [expr {$y-0.23}] [expr {$x+0.23}] [expr {$y+0.23}]
    via via1 $x $y
    rect metal3 [expr {$x-0.23}] [expr {$y-0.23}] [expr {$x+0.23}] [expr {$y+0.23}]
    via via2 $x $y
    rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]
    via via3 $x $y
}
proc terminal_to_m4 {x y} {
    # Diffusion terminal straps already contain M1 and Via1.  Do not paint a
    # second wide M1 landing here: it crowds adjacent alternating fingers.
    rect metal2 [expr {$x-0.23}] [expr {$y-0.23}] [expr {$x+0.23}] [expr {$y+0.23}]
    rect metal3 [expr {$x-0.23}] [expr {$y-0.23}] [expr {$x+0.23}] [expr {$y+0.23}]
    via via2 $x $y
    rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]
    via via3 $x $y
}
proc port_at {name number x y size} {
    rect metal5 [expr {$x-$size}] [expr {$y-$size}] [expr {$x+$size}] [expr {$y+$size}]
    label $name FreeSans 0.45 0 0 0 c metal5
    port make $number
}
proc gate_offsets {nf} {
    set points {}
    for {set index 0} {$index < $nf} {incr index} {
        lappend points [expr {-0.4*($nf-1)+0.8*$index}]
    }
    return $points
}
proc diffusion_offsets {nf parity} {
    set points {}
    for {set index 0} {$index <= $nf} {incr index} {
        if {$index % 2 == $parity} {
            lappend points [expr {-0.4*$nf+0.8*$index}]
        }
    }
    return $points
}
proc draw_mos {kind width nf cx cy} {
    set diffusion [expr {[string match "pfet*" $kind] ? "pdiff" : "ndiff"}]
    set contact [expr {[string match "pfet*" $kind] ? "pdc" : "ndc"}]
    set all_diff [lsort -real [concat [diffusion_offsets $nf 0] [diffusion_offsets $nf 1]]]
    rect $diffusion [expr {$cx+[lindex $all_diff 0]-0.18}] [expr {$cy-$width/2.0}] \
        [expr {$cx+[lindex $all_diff end]+0.18}] [expr {$cy+$width/2.0}]
    foreach offset [gate_offsets $nf] {
        set x [expr {$cx+$offset}]
        rect polysilicon [expr {$x-0.14}] [expr {$cy-$width/2.0-0.22}] \
            [expr {$x+0.14}] [expr {$cy+$width/2.0+0.22}]
    }
    foreach offset $all_diff {
        set x [expr {$cx+$offset}]
        rect $contact [expr {$x-0.115}] [expr {$cy-$width/2.0+0.065}] \
            [expr {$x+0.115}] [expr {$cy+$width/2.0-0.065}]
        rect metal1 [expr {$x-0.18}] [expr {$cy-$width/2.0}] \
            [expr {$x+0.18}] [expr {$cy+$width/2.0}]
    }
}
proc gate_contact {cx cy width nf} {
    set gy [expr {$cy-$width/2.0-0.35}]
    set points [gate_offsets $nf]
    set half [expr {$nf == 1 ? 0.22 : 0.4*$nf-0.25}]
    rect polysilicon [expr {$cx-$half}] $gy [expr {$cx+$half}] [expr {$gy+0.25}]
    foreach offset $points {
        set x [expr {$cx+$offset}]
        rect polysilicon [expr {$x-0.20}] [expr {$gy-0.65}] [expr {$x+0.20}] [expr {$gy+0.25}]
        rect polycontact [expr {$x-0.115}] [expr {$gy-0.565}] [expr {$x+0.115}] [expr {$gy-0.335}]
    }
    rect metal1 [expr {$cx+[lindex $points 0]-0.35}] [expr {$gy-0.65}] \
        [expr {$cx+[lindex $points end]+0.35}] [expr {$gy-0.05}]
    return [expr {$gy-0.35}]
}

# Place matching EVEN/ODD phase cells as mirrored columns.  Within each cell
# the output of the first inverter is the local complement rail and the second
# inverter produces the positive NFET-clock rail.
array set tracks {
    VSS -13.0
    E_WRITE -6.0
    O_WRITE 1.0
    E_CAPTURE_CLKB 10.0
    O_CAPTURE_CLKB 18.0
    E_CAPTURE_CLK 27.0
    O_CAPTURE_CLK 35.0
    VDD 76.0
}
array set net_min {}
array set net_max {}
set occupied {-44 -43 -42 -32 -31 -30 -20 -19 -18 -8 -7 -6 6 7 8 18 19 20 30 31 32 42 43 44}
array set columns {}
proc route_column {preferred net} {
    global occupied columns
    if {[info exists columns($net)]} { return $columns($net) }
    for {set radius 0} {$radius < 60} {incr radius} {
        foreach sign {1 -1} {
            if {$radius == 0 && $sign < 0} { continue }
            set candidate [expr {round(($preferred+$sign*0.8*$radius)*10.0)/10.0}]
            if {$candidate < -48 || $candidate > 48} { continue }
            set clear 1
            foreach used $occupied {
                if {abs($candidate-$used) < 0.79} { set clear 0; break }
            }
            if {$clear} {
                lappend occupied $candidate
                set columns($net) $candidate
                return $candidate
            }
        }
    }
    error "no M3 escape for $net"
}
proc connect {net x y} {
    global tracks net_min net_max
    set ty $tracks($net)
    rect metal3 [expr {$x-0.23}] [expr {min($y,$ty)-0.38}] \
        [expr {$x+0.23}] [expr {max($y,$ty)+0.38}]
    rect metal4 [expr {$x-0.38}] [expr {$ty-0.38}] [expr {$x+0.38}] [expr {$ty+0.38}]
    via via3 $x $ty
    if {![info exists net_min($net)] || $x < $net_min($net)} { set net_min($net) $x }
    if {![info exists net_max($net)] || $x > $net_max($net)} { set net_max($net) $x }
}

set devices {
    {XECLKB_N nfet_03v3 10 8 -24 1 E_CAPTURE_CLKB E_WRITE VSS}
    {XECLK_N nfet_03v3 5 16 -24 23 E_CAPTURE_CLK E_CAPTURE_CLKB VSS}
    {XECLKB_P pfet_03v3 8 8 -24 46 E_CAPTURE_CLKB E_WRITE VDD}
    {XECLK_P pfet_03v3 12 16 -24 64 E_CAPTURE_CLK E_CAPTURE_CLKB VDD}
    {XOCLKB_N nfet_03v3 10 8 24 1 O_CAPTURE_CLKB O_WRITE VSS}
    {XOCLK_N nfet_03v3 5 16 24 23 O_CAPTURE_CLK O_CAPTURE_CLKB VSS}
    {XOCLKB_P pfet_03v3 8 8 24 46 O_CAPTURE_CLKB O_WRITE VDD}
    {XOCLK_P pfet_03v3 12 16 24 64 O_CAPTURE_CLK O_CAPTURE_CLKB VDD}
}

crashbackups stop
load capture_clock_bridge
units microns
rect pwell -52 -20 52 33
rect nwell -52 33.2 52 80
foreach spec $devices {
    lassign $spec instance kind width nf cx cy drain gate source
    draw_mos $kind $width $nf $cx $cy
}
foreach spec $devices {
    lassign $spec instance kind width nf cx cy drain gate source
    set drain_points [diffusion_offsets $nf 0]
    set source_points [diffusion_offsets $nf 1]
    set yoff [expr {max(0.70,$width/2.0-0.8)}]
    set drain_y [expr {$cy+$yoff}]
    set source_y [expr {$cy-$yoff}]
    set drain_x [route_column [expr {$cx-1.6}] $drain]
    set source_x [route_column [expr {$cx+1.6}] $source]
    set gate_y [gate_contact $cx $cy $width $nf]
    set gate_x [route_column $cx $gate]
    rect metal2 [expr {min($drain_x,$cx+[lindex $drain_points 0])-0.38}] [expr {$drain_y-0.38}] \
        [expr {max($drain_x,$cx+[lindex $drain_points end])+0.38}] [expr {$drain_y+0.38}]
    rect metal2 [expr {min($source_x,$cx+[lindex $source_points 0])-0.38}] [expr {$source_y-0.38}] \
        [expr {max($source_x,$cx+[lindex $source_points end])+0.38}] [expr {$source_y+0.38}]
    foreach offset $drain_points {
        set x [expr {$cx+$offset}]
        rect metal1 [expr {$x-0.28}] [expr {$cy-0.28}] [expr {$x+0.28}] [expr {$drain_y+0.28}]
        via via1 $x $drain_y
    }
    foreach offset $source_points {
        set x [expr {$cx+$offset}]
        rect metal1 [expr {$x-0.28}] [expr {$source_y-0.28}] [expr {$x+0.28}] [expr {$cy+0.28}]
        via via1 $x $source_y
    }
    terminal_to_m4 $drain_x $drain_y
    terminal_to_m4 $source_x $source_y
    stack_to_m4 $gate_x $gate_y
    rect metal1 [expr {min($gate_x,$cx+[lindex [gate_offsets $nf] 0])-0.35}] [expr {$gate_y-0.30}] \
        [expr {max($gate_x,$cx+[lindex [gate_offsets $nf] end])+0.35}] [expr {$gate_y+0.30}]
    connect $drain $drain_x $drain_y
    connect $source $source_x $source_y
    connect $gate $gate_x $gate_y
}

# Complete the M4 buses, then make high-metal pad-facing access points.
foreach net [array names net_min] {
    set y $tracks($net)
    set half [expr {$net eq "VDD" || $net eq "VSS" ? 0.42 : 0.28}]
    rect metal4 [expr {$net_min($net)-0.45}] [expr {$y-$half}] \
        [expr {$net_max($net)+0.45}] [expr {$y+$half}]
    label $net FreeSans 0.30 0 0 0 c metal4
}

# Dense, explicit body contacts and supply rings keep the bridge independent of
# parent fill and make its dynamic clock return path visible to extraction.
foreach x {-44 -32 -20 -8 8 20 32 44} {
    rect psubdiff [expr {$x-0.32}] -17.4 [expr {$x+0.32}] -16.6
    rect psubdiffcont [expr {$x-0.25}] -17.3 [expr {$x+0.25}] -16.7
    stack_to_m4 $x -17
    rect nsubdiff [expr {$x-0.32}] 78.0 [expr {$x+0.32}] 78.7
    rect nsubdiffcont [expr {$x-0.25}] 78.1 [expr {$x+0.25}] 78.6
    stack_to_m4 $x 78.4
    via via4 $x 78.4
    via via4 $x -17
}
# The substrate guard is VSS only and stops above the NFET pwell.  Keep it
# physically disjoint from the VDD-connected nwell-contact rail at y=78.
rect metal5 -45 -17.45 45 -16.55
rect metal5 -45 -17.45 -44.2 33.0
rect metal5 44.2 -17.45 45 33.0
rect metal5 -45 32.2 45 33.0
rect metal5 -45 78.0 45 78.8
rect metal5 -44.6 -17.0 -43.8 -13.0
rect metal5 43.8 76.0 44.6 78.4
via via4 -44.2 -13.0
via via4 44.2 76.0

foreach {name number x} {
    E_WRITE 1 -50 O_WRITE 2 50 E_CAPTURE_CLK 3 -48 E_CAPTURE_CLKB 4 -46
    O_CAPTURE_CLK 5 48 O_CAPTURE_CLKB 6 46
} {
    set y $tracks($name)
    rect metal4 [expr {min($x,$net_min($name))-0.38}] [expr {$y-0.38}] \
        [expr {max($x,$net_max($name))+0.38}] [expr {$y+0.38}]
    rect metal4 [expr {$x-0.55}] [expr {$y-0.55}] [expr {$x+0.55}] [expr {$y+0.55}]
    via via4 $x $y
    port_at $name $number $x $y 0.48
}
rect metal4 [expr {$net_min(VDD)-0.38}] 75.62 50.55 76.38
rect metal4 -50.55 -13.38 [expr {$net_max(VSS)+0.38}] -12.62
rect metal4 49.45 75.45 50.55 76.55
rect metal4 -50.55 -13.55 -49.45 -12.45
rect metal5 43.65 75.45 44.75 76.55
rect metal5 -44.75 -13.55 -43.65 -12.45
via via4 44.2 76.0
via via4 -44.2 -13.0
via via4 50.0 76.0
via via4 -50.0 -13.0
port_at VDD 7 50.0 76.0 0.60
port_at VSS 8 -50.0 -13.0 0.60

# Contacted substrate guard ring encloses the NFET area; the nwell perimeter
# remains equally distant from the matched EVEN/ODD PMOS columns.
rect psubdiff -52 -20 -51.2 33
rect psubdiff 51.2 -20 52 33
rect psubdiff -52 -20 52 -19.2
rect psubdiff -52 32.2 52 33
rect metal1 -52 -20 -51.2 33
rect metal1 51.2 -20 52 33
rect metal1 -52 -20 52 -19.2
rect metal1 -52 32.2 52 33
foreach x {-48 -36 -24 -12 0 12 24 36 48} {
    rect psubdiffcont [expr {$x-0.25}] -19.7 [expr {$x+0.25}] -19.3
    rect psubdiffcont [expr {$x-0.25}] 32.5 [expr {$x+0.25}] 32.9
}
save /work/capture_clock_bridge
gds write /work/capture_clock_bridge.gds
quit -noprompt
