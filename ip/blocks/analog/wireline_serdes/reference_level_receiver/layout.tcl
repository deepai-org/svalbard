# SPDX-License-Identifier: Apache-2.0
# Compact matched GF180 single-ended reference level receiver.

proc rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}

proc via {layer x y} {
    rect $layer [expr {$x-0.18}] [expr {$y-0.18}] \
        [expr {$x+0.18}] [expr {$y+0.18}]
}

proc stack {x y highest} {
    rect metal1 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    rect metal2 [expr {$x-0.23}] [expr {$y-0.23}] \
        [expr {$x+0.23}] [expr {$y+0.23}]
    via via1 $x $y
    if {$highest >= 3} {
        rect metal3 [expr {$x-0.23}] [expr {$y-0.23}] \
            [expr {$x+0.23}] [expr {$y+0.23}]
        via via2 $x $y
    }
    if {$highest >= 4} {
        rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
        via via3 $x $y
    }
    if {$highest >= 5} {
        rect metal5 [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
        via via4 $x $y
    }
}

proc make_port {name number layer x y size} {
    rect $layer [expr {$x-$size}] [expr {$y-$size}] \
        [expr {$x+$size}] [expr {$y+$size}]
    box values [expr {$x-$size}] [expr {$y-$size}] \
        [expr {$x+$size}] [expr {$y+$size}]
    label $name FreeSans 0.5 0 0 0 c $layer
    port make $number
}

proc pcontact {x y} {
    rect psubdiffcont [expr {$x-0.25}] [expr {$y-0.30}] \
        [expr {$x+0.25}] [expr {$y+0.30}]
}

proc ncontact {x y} {
    rect nsubdiffcont [expr {$x-0.25}] [expr {$y-0.30}] \
        [expr {$x+0.25}] [expr {$y+0.30}]
}

proc diff_offsets {nf parity} {
    set answer {}
    set index 0
    for {set x [expr {-0.4*$nf}]} {$index <= $nf} \
            {set x [expr {$x+0.8}]; incr index} {
        if {$index % 2 == $parity} { lappend answer $x }
    }
    return $answer
}

proc gate_offsets {nf} {
    set answer {}
    for {set index 0} {$index < $nf} {incr index} {
        lappend answer [expr {-0.4*($nf-1)+0.8*$index}]
    }
    return $answer
}

proc draw_mos {kind width nf cx cy} {
    set diffusion [expr {[string match "pfet*" $kind] ? "pdiff" : "ndiff"}]
    set contact [expr {[string match "pfet*" $kind] ? "pdc" : "ndc"}]
    set xs [lsort -real [concat [diff_offsets $nf 0] [diff_offsets $nf 1]]]
    set left [expr {$cx+[lindex $xs 0]}]
    set right [expr {$cx+[lindex $xs end]}]
    rect $diffusion [expr {$left-0.18}] [expr {$cy-$width/2.0}] \
        [expr {$right+0.18}] [expr {$cy+$width/2.0}]
    foreach xoff [gate_offsets $nf] {
        set x [expr {$cx+$xoff}]
        rect polysilicon [expr {$x-0.14}] [expr {$cy-$width/2.0-0.22}] \
            [expr {$x+0.14}] [expr {$cy+$width/2.0+0.22}]
    }
    foreach xoff $xs {
        set x [expr {$cx+$xoff}]
        rect $contact [expr {$x-0.115}] [expr {$cy-$width/2.0+0.065}] \
            [expr {$x+0.115}] [expr {$cy+$width/2.0-0.065}]
        rect metal1 [expr {$x-0.18}] [expr {$cy-$width/2.0}] \
            [expr {$x+0.18}] [expr {$cy+$width/2.0}]
    }
}

proc manual_gate {cx cy width nf} {
    set extra [expr {$width < 2.0 ? 0.42 : 0.0}]
    set y [expr {$cy-$width/2.0-0.70-$extra}]
    set xs [gate_offsets $nf]
    set half [expr {$nf == 1 ? 0.22 : 0.4*$nf-0.25}]
    rect polysilicon [expr {$cx-$half}] [expr {$y+0.35}] \
        [expr {$cx+$half}] [expr {$y+0.60+$extra}]
    foreach xoff $xs {
        set x [expr {$cx+$xoff}]
        rect polysilicon [expr {$x-0.20}] [expr {$y-0.30}] \
            [expr {$x+0.20}] [expr {$y+0.60+$extra}]
        rect polycontact [expr {$x-0.115}] [expr {$y-0.215}] \
            [expr {$x+0.115}] [expr {$y+0.015}]
    }
    rect metal1 [expr {$cx+[lindex $xs 0]-0.35}] [expr {$y-0.30}] \
        [expr {$cx+[lindex $xs end]+0.35}] [expr {$y+0.30}]
    return $y
}

array set tracks {
    VSS -34.0 IN -24.0 REF -22.4 VBIAS -20.8
    TAIL -16.0 N1 -12.8 N2 9.6 A 11.2 MIDP 12.8 MIDN 14.4
    OUTN 20.0 OUTP 21.6 VDD 72.0
}
array set net_min {}
array set net_max {}
array set net_columns {}
set used_columns {
    -61 -60 -59 -58 -57 -56 -55 -54 -53 -43 -42 -41 -25 -24 -23
    -1 0 1 23 24 25 41 42 43 53 54 55 56 57 58 59 60 61
}

proc route_column {preferred net} {
    global used_columns net_columns
    if {[info exists net_columns($net)]} {
        set best [lindex $net_columns($net) 0]
        set distance [expr {abs($preferred-$best)}]
        foreach x $net_columns($net) {
            if {abs($preferred-$x) < $distance} {
                set best $x
                set distance [expr {abs($preferred-$x)}]
            }
        }
        if {$distance <= 5.0} { return $best }
    }
    for {set radius 0} {$radius < 160} {incr radius} {
        foreach sign {1 -1} {
            if {$radius == 0 && $sign < 0} { continue }
            set x [expr {round(($preferred+$sign*$radius)*10.0)/10.0}]
            if {$x < -58 || $x > 58} { continue }
            set legal 1
            foreach occupied $used_columns {
                if {abs($x-$occupied) < 0.99} { set legal 0; break }
            }
            if {$legal} {
                lappend used_columns $x
                lappend net_columns($net) $x
                return $x
            }
        }
    }
    error "no M3 route column for $net near $preferred"
}

proc m2_m3 {x y} {
    rect metal2 [expr {$x-0.23}] [expr {$y-0.23}] \
        [expr {$x+0.23}] [expr {$y+0.23}]
    rect metal3 [expr {$x-0.23}] [expr {$y-0.23}] \
        [expr {$x+0.23}] [expr {$y+0.23}]
    via via2 $x $y
}

proc connect {net x y} {
    global tracks net_min net_max
    set ty $tracks($net)
    rect metal3 [expr {$x-0.23}] [expr {min($y,$ty)-0.38}] \
        [expr {$x+0.23}] [expr {max($y,$ty)+0.38}]
    rect metal4 [expr {$x-0.38}] [expr {$ty-0.38}] \
        [expr {$x+0.38}] [expr {$ty+0.38}]
    via via3 $x $ty
    if {![info exists net_min($net)] || $x < $net_min($net)} { set net_min($net) $x }
    if {![info exists net_max($net)] || $x > $net_max($net)} { set net_max($net) $x }
}

# instance kind finger-width finger-count x y drain gate source
# The signal/reference pair and mirror loads are adjacent, symmetric about x=0,
# and protected by equal edge dummies.  The inverter taper is kept outside it.
set devices {
    {XDNL nfet_03v3 8 1 -18 0 VSS VSS VSS}
    {XIS nfet_03v3 8 1 -6 0 N1 IN TAIL}
    {XIR nfet_03v3 8 1 6 0 N2 REF TAIL}
    {XDNR nfet_03v3 8 1 18 0 VSS VSS VSS}
    {XTAIL nfet_03v3 12 2 0 -18 TAIL VBIAS VSS}
    {XISO_N nfet_03v3 2 1 -46 18 A N2 VSS}
    {XGAIN_N nfet_03v3 6 2 -38 18 MIDP A VSS}
    {XPHASE_N nfet_03v3 4 1 28 18 MIDN MIDP VSS}
    {XOUTN_N nfet_03v3 6 2 40 18 OUTN MIDP VSS}
    {XOUTP_N nfet_03v3 6 2 52 18 OUTP MIDN VSS}

    {XDPL pfet_03v3 8 1 -18 48 VDD VDD VDD}
    {XPL pfet_03v3 8 1 -6 48 N1 N1 VDD}
    {XPR pfet_03v3 8 1 6 48 N2 N1 VDD}
    {XDPR pfet_03v3 8 1 18 48 VDD VDD VDD}
    {XISO_P pfet_03v3 4 1 -46 58 A N2 VDD}
    {XGAIN_P pfet_03v3 8 2 -38 58 MIDP A VDD}
    {XPHASE_P pfet_03v3 8 1 28 58 MIDN MIDP VDD}
    {XOUTN_P pfet_03v3 8 3 40 58 OUTN MIDP VDD}
    {XOUTP_P pfet_03v3 8 3 52 58 OUTP MIDN VDD}
}

crashbackups stop
load reference_level_receiver
units microns
rect pwell -62 -40 62 31
rect nwell -63 32 63 77

foreach spec $devices {
    lassign $spec instance kind width nf cx cy drain gate source
    draw_mos $kind $width $nf $cx $cy
}

foreach spec $devices {
    lassign $spec instance kind width nf cx cy drain gate source
    set yoff [expr {max(0.70,$width/2.0-0.8)}]
    set drain_y [expr {$cy+$yoff}]
    set source_y [expr {$cy-$yoff}]
    set drain_points {}
    set source_points {}
    foreach xoff [diff_offsets $nf 0] {
        set x [expr {$cx+$xoff}]
        rect metal1 [expr {$x-0.28}] [expr {$cy-0.28}] \
            [expr {$x+0.28}] [expr {$drain_y+0.28}]
        via via1 $x $drain_y
        rect metal2 [expr {$x-0.28}] [expr {$drain_y-0.28}] \
            [expr {$x+0.28}] [expr {$drain_y+0.28}]
        lappend drain_points $x
    }
    foreach xoff [diff_offsets $nf 1] {
        set x [expr {$cx+$xoff}]
        rect metal1 [expr {$x-0.28}] [expr {$source_y-0.28}] \
            [expr {$x+0.28}] [expr {$cy+0.28}]
        via via1 $x $source_y
        rect metal2 [expr {$x-0.28}] [expr {$source_y-0.28}] \
            [expr {$x+0.28}] [expr {$source_y+0.28}]
        lappend source_points $x
    }
    set gate_y [manual_gate $cx $cy $width $nf]
    set drain_route [route_column [expr {$cx-0.8}] $drain]
    set source_route [route_column [expr {$cx+0.8}] $source]
    set gate_route [route_column $cx $gate]
    if {[info exists ::env(LAYOUT_ROUTE_DEBUG)]} {
        puts "ROUTE $instance d=$drain:$drain_route g=$gate:$gate_route s=$source:$source_route"
    }
    rect metal2 [expr {min($drain_route,[lindex $drain_points 0])-0.38}] \
        [expr {$drain_y-0.38}] \
        [expr {max($drain_route,[lindex $drain_points end])+0.38}] \
        [expr {$drain_y+0.38}]
    rect metal2 [expr {min($source_route,[lindex $source_points 0])-0.38}] \
        [expr {$source_y-0.38}] \
        [expr {max($source_route,[lindex $source_points end])+0.38}] \
        [expr {$source_y+0.38}]
    m2_m3 $drain_route $drain_y
    m2_m3 $source_route $source_y
    connect $drain $drain_route $drain_y
    connect $source $source_route $source_y
    set gates [gate_offsets $nf]
    rect metal1 [expr {min($gate_route,$cx+[lindex $gates 0])-0.35}] \
        [expr {$gate_y-0.30}] \
        [expr {max($gate_route,$cx+[lindex $gates end])+0.35}] \
        [expr {$gate_y+0.30}]
    stack $gate_route $gate_y 3
    connect $gate $gate_route $gate_y
}

# Distributed body contacts: local tap columns plus contacted perimeter rails.
foreach x {-54 -42 -24 0 24 42 54} {
    rect psubdiff [expr {$x-0.32}] -29.37 [expr {$x+0.32}] -28.63
    pcontact $x -29
    stack $x -29 3
    rect nsubdiff [expr {$x-0.32}] 69.63 [expr {$x+0.32}] 70.37
    ncontact $x 70
    stack $x 70 3
}
rect metal4 -54.38 [expr {$tracks(VSS)-0.38}] 60.38 [expr {$tracks(VSS)+0.38}]
rect metal3 -54.28 -34.28 -53.72 -28.72
via via3 -54 $tracks(VSS)
rect metal4 -54.38 [expr {$tracks(VDD)-0.38}] 60.38 [expr {$tracks(VDD)+0.38}]
rect metal3 -54.28 69.72 -53.72 72.28
via via3 -54 $tracks(VDD)

rect psubdiff -62 -40 -61.2 31
rect psubdiff 61.2 -40 62 31
rect psubdiff -62 -40 62 -39.2
rect psubdiff -62 30.2 62 31
rect metal1 -62 -40 -61.2 31
rect metal1 61.2 -40 62 31
rect metal1 -62 -40 62 -39.2
rect metal1 -62 30.2 62 31
foreach x {-57 -45 -33 -21 -9 3 15 27 39 51} {
    pcontact $x -39.6
    pcontact $x 30.6
}
foreach y {-35 -23 -11 1 13 25} {
    pcontact -61.6 $y
    pcontact 61.6 $y
}
stack 61.6 -39.6 5
rect metal5 59.62 -39.98 61.98 -39.22
rect metal5 59.62 -39.6 60.38 -34.0

rect nsubdiff -62 75.2 62 76
rect metal1 -62 75.2 62 76
foreach x {-57 -45 -33 -21 -9 3 15 27 39 51} {
    ncontact $x 75.6
    stack $x 75.6 5
}
rect metal5 -62 75.2 62 76
rect metal5 -60.38 72.0 -59.62 75.6

foreach {name number x} {
    IN 1 -60 REF 2 -58 VBIAS 3 -56
    OUTP 6 58 OUTN 7 60
} {
    connect $name $x $tracks($name)
    via via4 $x $tracks($name)
    make_port $name $number metal5 $x $tracks($name) 0.45
}
foreach {name number x} {VDD 4 -60 VSS 5 60} {
    connect $name $x $tracks($name)
    via via4 $x $tracks($name)
    make_port $name $number metal5 $x $tracks($name) 0.55
}

# Build one M4 bus per net after device accesses and pins establish bounds.
foreach net [array names net_min] {
    set y $tracks($net)
    set half [expr {$net eq "VDD" || $net eq "VSS" ? 0.38 : 0.23}]
    rect metal4 [expr {$net_min($net)-0.38}] [expr {$y-$half}] \
        [expr {$net_max($net)+0.38}] [expr {$y+$half}]
}

save /work/reference_level_receiver
gds write /work/reference_level_receiver.gds
quit -noprompt
