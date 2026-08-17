# SPDX-License-Identifier: Apache-2.0
# Symmetric held CML-to-CMOS retimer layout for GF180MCU.

proc paint_rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}

proc via_at {layer x y} {
    paint_rect $layer [expr {$x-0.18}] [expr {$y-0.18}] \
        [expr {$x+0.18}] [expr {$y+0.18}]
}

proc stack_to {x y highest} {
    paint_rect metal1 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    paint_rect metal2 [expr {$x-0.23}] [expr {$y-0.23}] \
        [expr {$x+0.23}] [expr {$y+0.23}]
    via_at via1 $x $y
    if {$highest >= 3} {
        paint_rect metal3 [expr {$x-0.23}] [expr {$y-0.23}] \
            [expr {$x+0.23}] [expr {$y+0.23}]
        via_at via2 $x $y
    }
    if {$highest >= 4} {
        paint_rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
        via_at via3 $x $y
    }
    if {$highest >= 5} {
        paint_rect metal5 [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
        via_at via4 $x $y
    }
}

proc make_port {name number layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
    label $name FreeSans 0.5 0 0 0 c $layer
    port make $number
}

proc substrate_contact {x y} {
    paint_rect psubdiffcont [expr {$x-0.25}] [expr {$y-0.30}] \
        [expr {$x+0.25}] [expr {$y+0.30}]
}

proc nwell_contact {x y} {
    paint_rect nsubdiffcont [expr {$x-0.25}] [expr {$y-0.30}] \
        [expr {$x+0.25}] [expr {$y+0.30}]
}

proc diffusion_offsets {nf parity} {
    set result {}
    set index 0
    for {set x [expr {-0.4*$nf}]} {$index <= $nf} \
            {set x [expr {$x+0.8}]; incr index} {
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

proc terminal_strap {cx cy yoff xs} {
    set y [expr {$cy+$yoff}]
    foreach xoff $xs {
        set x [expr {$cx+$xoff}]
        paint_rect metal1 [expr {$x-0.30}] [expr {$y-0.30}] \
            [expr {$x+0.30}] [expr {$y+0.30}]
        via_at via1 $x $y
    }
    paint_rect metal2 [expr {$cx+[lindex $xs 0]-0.38}] [expr {$y-0.38}] \
        [expr {$cx+[lindex $xs end]+0.38}] [expr {$y+0.38}]
}

proc m2_to_m3 {x y} {
    paint_rect metal2 [expr {$x-0.23}] [expr {$y-0.23}] \
        [expr {$x+0.23}] [expr {$y+0.23}]
    paint_rect metal3 [expr {$x-0.23}] [expr {$y-0.23}] \
        [expr {$x+0.23}] [expr {$y+0.23}]
    via_at via2 $x $y
}

# Allocate one globally unique M3 access column to each logical terminal.
# A 0.8 um grid leaves 0.34 um between minimum legal Via3 landings.
set used_route_columns {}
proc route_column {preferred} {
    global used_route_columns
    for {set radius 0} {$radius < 400} {incr radius} {
        foreach sign {1 -1} {
            if {$radius == 0 && $sign < 0} { continue }
            set candidate [expr {round(($preferred+$sign*0.8*$radius)*10.0)/10.0}]
            if {$candidate < -64.0 || $candidate > 64.0} { continue }
            set available 1
            foreach occupied $used_route_columns {
                if {abs($candidate-$occupied) < 0.79} {
                    set available 0
                    break
                }
            }
            if {$available} {
                lappend used_route_columns $candidate
                return $candidate
            }
        }
    }
    error "No legal M3 access column near $preferred"
}

proc manual_gate {cx cy width nf} {
    set gy [expr {$cy-$width/2.0-0.35}]
    set xs [gate_offsets $nf]
    set half_width [expr {$nf == 1 ? 0.22 : 0.4*$nf-0.25}]
    paint_rect polysilicon [expr {$cx-$half_width}] $gy \
        [expr {$cx+$half_width}] [expr {$gy+0.25}]
    foreach xoff $xs {
        set x [expr {$cx+$xoff}]
        paint_rect polysilicon [expr {$x-0.20}] [expr {$gy-0.65}] \
            [expr {$x+0.20}] [expr {$gy+0.25}]
        paint_rect polycontact [expr {$x-0.115}] [expr {$gy-0.565}] \
            [expr {$x+0.115}] [expr {$gy-0.335}]
    }
    paint_rect metal1 [expr {$cx+[lindex $xs 0]-0.35}] [expr {$gy-0.65}] \
        [expr {$cx+[lindex $xs end]+0.35}] [expr {$gy-0.05}]
    return [expr {$gy-0.35}]
}

array set tracks {
    VSS -20.0 INP -3.6 INN -2.2 SENSE_CLK -0.8 NTAIL 0.6
    XP 2.0 XN 3.4 QP 7.6 QN 9.0
    OUTP 27.0 OUTN 28.4 VDD 67.0
}
array set net_min {}
array set net_max {}

proc connect_net {net x y} {
    global tracks net_min net_max
    set ty $tracks($net)
    set half_width [expr {$net eq "VDD" || $net eq "VSS" ? 0.23 : 0.14}]
    paint_rect metal3 [expr {$x-$half_width}] [expr {min($y,$ty)-0.38}] \
        [expr {$x+$half_width}] [expr {max($y,$ty)+0.38}]
    # Via3 needs a legal Metal3 landing.  Keep the long access wire narrow,
    # but widen only at the M3/M4 transition instead of widening the full run.
    paint_rect metal3 [expr {$x-0.23}] [expr {$ty-0.23}] \
        [expr {$x+0.23}] [expr {$ty+0.23}]
    paint_rect metal4 [expr {$x-0.38}] [expr {$ty-0.38}] \
        [expr {$x+0.38}] [expr {$ty+0.38}]
    via_at via3 $x $ty
    if {![info exists net_min($net)] || $x < $net_min($net)} { set net_min($net) $x }
    if {![info exists net_max($net)] || $x > $net_max($net)} { set net_max($net) $x }
}

proc device_cell {kind width nf} {
    global device_cells
    set key "${kind}_${width}_${nf}"
    if {![info exists device_cells($key)]} {
        set device_cells($key) [magic::gencell_makecell gf180mcu::$kind \
            w $width l 0.28 nf $nf guard 0 topc 0 botc 0 full_metal 0]
    }
    return $device_cells($key)
}

proc finger_groups {nf cx} {
    return [list [list 0 $cx $nf]]
}

proc draw_shared_mos {kind width nf cx cy} {
    set diff_layer [expr {[string match "pfet*" $kind] ? "pdiff" : "ndiff"}]
    set contact_layer [expr {[string match "pfet*" $kind] ? "pdc" : "ndc"}]
    set diffusion_xs [diffusion_offsets $nf 0]
    set diffusion_xs [concat $diffusion_xs [diffusion_offsets $nf 1]]
    set diffusion_xs [lsort -real $diffusion_xs]
    set left [expr {$cx+[lindex $diffusion_xs 0]}]
    set right [expr {$cx+[lindex $diffusion_xs end]}]
    paint_rect $diff_layer [expr {$left-0.18}] [expr {$cy-$width/2.0}] \
        [expr {$right+0.18}] [expr {$cy+$width/2.0}]
    foreach xoff [gate_offsets $nf] {
        set x [expr {$cx+$xoff}]
        paint_rect polysilicon [expr {$x-0.14}] [expr {$cy-$width/2.0-0.22}] \
            [expr {$x+0.14}] [expr {$cy+$width/2.0+0.22}]
    }
    foreach xoff $diffusion_xs {
        set x [expr {$cx+$xoff}]
        paint_rect $contact_layer [expr {$x-0.115}] \
            [expr {$cy-$width/2.0+0.065}] [expr {$x+0.115}] \
            [expr {$cy+$width/2.0-0.065}]
        paint_rect metal1 [expr {$x-0.18}] [expr {$cy-$width/2.0}] \
            [expr {$x+0.18}] [expr {$cy+$width/2.0}]
    }
}

# instance kind width fingers x y drain gate source
set devices {
    {XOPP pfet_03v3 8 3 -50 35 OUTP QN VDD}
    {XONP pfet_03v3 8 3  50 35 OUTN QP VDD}
    {XPREP  pfet_03v3 8 4  -12 55 XP SENSE_CLK VDD}
    {XPREN  pfet_03v3 8 4   12 55 XN SENSE_CLK VDD}
    {XEQUAL pfet_03v3 8 4    0 55 XP SENSE_CLK XN}
    {XLATP pfet_03v3 8 5 -12 45 XP XN VDD}
    {XLATN pfet_03v3 8 5  12 45 XN XP VDD}

    {XLP pfet_03v3 4 1 -18 35 QP QN VDD}
    {XRP pfet_03v3 4 1  18 35 QN QP VDD}
    {XSP pfet_03v3 8 4 -28 35 QP XP VDD}
    {XSN pfet_03v3 8 4  28 35 QN XN VDD}

    {XIP nfet_03v3 8 2 -14 10 XP INP NTAIL}
    {XIN nfet_03v3 8 2  14 10 XN INN NTAIL}
    {XREGENP nfet_03v3 8 3 -24 10 XP XN NTAIL}
    {XREGENN nfet_03v3 8 3  24 10 XN XP NTAIL}
    {XTAIL nfet_03v3 8 8 0 10 NTAIL SENSE_CLK VSS}

    {XLN nfet_03v3 4 1 -18 22 QP QN VSS}
    {XRN nfet_03v3 4 1  18 22 QN QP VSS}
    {XOPN nfet_03v3 8 1 -50 22 OUTP QN VSS}
    {XONN nfet_03v3 8 1  50 22 OUTN QP VSS}
}

crashbackups stop
load cml_to_cmos
units microns
paint_rect pwell -75 -70 75 29
paint_rect nwell -75 30 75 90

foreach spec $devices {
    lassign $spec instance kind width nf cx cy drain gate source
    draw_shared_mos $kind $width $nf $cx $cy
}

foreach spec $devices {
    lassign $spec instance kind width nf cx cy drain gate source
    set drain_points {}
    set source_points {}
    set gate_points {}
    foreach group [finger_groups $nf $cx] {
        lassign $group index gx group_nf
        set yoff [expr {max(0.70,$width/2.0-0.8)}]
        # The GF180 MOS PCell places drain and source diffusion contacts on
        # the west/east sides of an nf=1 device.  Escape them vertically on
        # M1 before forming the separate drain/source M2 straps.
        set drain_y [expr {$cy+$yoff}]
        set source_y [expr {$cy-$yoff}]
        foreach xoff [diffusion_offsets $group_nf 0] {
            set drain_x [expr {$gx+$xoff}]
            paint_rect metal1 [expr {$drain_x-0.28}] [expr {$cy-0.28}] \
                [expr {$drain_x+0.28}] [expr {$drain_y+0.28}]
            via_at via1 $drain_x $drain_y
            paint_rect metal2 [expr {$drain_x-0.28}] [expr {$drain_y-0.28}] \
                [expr {$drain_x+0.28}] [expr {$drain_y+0.28}]
            lappend drain_points $drain_x
        }
        foreach xoff [diffusion_offsets $group_nf 1] {
            set source_x [expr {$gx+$xoff}]
            paint_rect metal1 [expr {$source_x-0.28}] [expr {$source_y-0.28}] \
                [expr {$source_x+0.28}] [expr {$cy+0.28}]
            via_at via1 $source_x $source_y
            paint_rect metal2 [expr {$source_x-0.28}] [expr {$source_y-0.28}] \
                [expr {$source_x+0.28}] [expr {$source_y+0.28}]
            lappend source_points $source_x
        }
        set gate_y [manual_gate $gx $cy $width $group_nf]
        foreach xoff [gate_offsets $group_nf] {
            lappend gate_points [expr {$gx+$xoff}]
        }
    }

    set drain_y [expr {$cy+$yoff}]
    set source_y [expr {$cy-$yoff}]
    set gate_y [expr {$cy-$width/2.0-0.70}]
    set drain_route [route_column [expr {$cx-0.8}]]
    set source_route [route_column [expr {$cx+0.8}]]
    set gate_route [route_column $cx]
    set source_routes [list $source_route]
    if {($source eq "VDD" || $source eq "VSS") && $nf >= 8} {
        lappend source_routes [route_column [expr {$cx+2.4}]]
    }

    paint_rect metal2 [expr {min($drain_route,[lindex $drain_points 0])-0.38}] \
        [expr {$drain_y-0.38}] \
        [expr {max($drain_route,[lindex $drain_points end])+0.38}] \
        [expr {$drain_y+0.38}]
    set source_route_min $source_route
    set source_route_max $source_route
    foreach tap $source_routes {
        if {$tap < $source_route_min} { set source_route_min $tap }
        if {$tap > $source_route_max} { set source_route_max $tap }
    }
    paint_rect metal2 [expr {min($source_route_min,[lindex $source_points 0])-0.38}] \
        [expr {$source_y-0.38}] \
        [expr {max($source_route_max,[lindex $source_points end])+0.38}] \
        [expr {$source_y+0.38}]
    m2_to_m3 $drain_route $drain_y
    connect_net $drain $drain_route $drain_y
    foreach tap $source_routes {
        m2_to_m3 $tap $source_y
        connect_net $source $tap $source_y
    }

    paint_rect metal1 [expr {min($gate_route,[lindex $gate_points 0])-0.35}] \
        [expr {$gate_y-0.30}] \
        [expr {max($gate_route,[lindex $gate_points end])+0.35}] \
        [expr {$gate_y+0.30}]
    stack_to $gate_route $gate_y 3
    connect_net $gate $gate_route $gate_y
}

# External pins participate in the same compact M4 net buses.
foreach {name number x} {INP 1 -73 INN 2 -71 SENSE_CLK 3 -69 OUTP 6 69 OUTN 7 71} {
    connect_net $name $x $tracks($name)
    via_at via4 $x $tracks($name)
    make_port $name $number metal5 [expr {$x-0.45}] [expr {$tracks($name)-0.45}] \
        [expr {$x+0.45}] [expr {$tracks($name)+0.45}]
}
foreach {name number x} {VDD 4 -67 VSS 5 67} {
    connect_net $name $x $tracks($name)
    via_at via4 $x $tracks($name)
    make_port $name $number metal5 [expr {$x-0.55}] [expr {$tracks($name)-0.55}] \
        [expr {$x+0.55}] [expr {$tracks($name)+0.55}]
}

foreach net [array names net_min] {
    set y $tracks($net)
    paint_rect metal4 [expr {$net_min($net)-0.38}] [expr {$y-0.38}] \
        [expr {$net_max($net)+0.38}] [expr {$y+0.38}]
    box values [expr {$net_min($net)-0.20}] [expr {$y-0.20}] \
        [expr {$net_min($net)+0.20}] [expr {$y+0.20}]
    label $net FreeSans 0.30 0 0 0 c metal4
}

# Contact the common PMOS well frequently and tie it to the VDD port on M5.
paint_rect nsubdiff -73 87.95 73 88.85
paint_rect metal1 -73 87.95 73 88.85
foreach x {-70 -54 -38 -22 -6 10 26 42 58 70} {
    nwell_contact $x 88.4
    stack_to $x 88.4 5
}
paint_rect metal5 -73 87.95 73 88.85
paint_rect metal5 -67.38 67.0 -66.62 88.85

# A contacted substrate guard ring provides explicit body and VSS return.
paint_rect psubdiff -75 -70 -74.2 29
paint_rect psubdiff 74.2 -70 75 29
paint_rect psubdiff -75 -70 75 -69.2
paint_rect psubdiff -75 28.2 75 29
paint_rect metal1 -75 -70 -74.2 29
paint_rect metal1 74.2 -70 75 29
paint_rect metal1 -75 -70 75 -69.2
paint_rect metal1 -75 28.2 75 29
foreach x {-70 -54 -38 -22 -6 10 26 42 58 70} {
    substrate_contact $x -69.6
    substrate_contact $x 28.6
}
foreach y {-66 -54 -42 -30 -18 -6 6 18 27} {
    substrate_contact -74.6 $y
    substrate_contact 74.6 $y
}
stack_to 74.6 -69.6 5
paint_rect metal5 67.0 -69.98 74.98 -69.22
paint_rect metal5 66.62 -69.6 67.38 -20.0

save /work/cml_to_cmos
gds write /work/cml_to_cmos.gds
quit -noprompt
