# SPDX-License-Identifier: Apache-2.0
# Symmetric dual-lane differential deserializer layout for GF180MCU.

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
# Reserve sparse body-tap columns before assigning signal escapes.  The tap
# columns are intentionally regular so latch-up distance is a geometric
# invariant rather than an accident of route-column allocation order.
set used_route_columns {
    -84.8 -84 -83.2 -60.8 -60 -59.2 -36.8 -36 -35.2
    -21.8 -21 -20.2 -12.8 -12 -11.2 -0.8 0 0.8
    11.2 12 12.8 20.2 21 21.8 35.2 36 36.8
    -56.8 59.2 60 60.8 63.2 83.2 84 84.8
}
array set net_route_columns {}
proc route_column {preferred net {force_new 0}} {
    global used_route_columns net_route_columns
    # Reuse a nearby vertical escape for repeated terminals on the same net.
    # This keeps same-row M2 terminal straps local instead of consuming a
    # globally unique column and eventually crossing unrelated devices.
    if {!$force_new && [info exists net_route_columns($net)]} {
        set best {}
        set best_distance 1e9
        foreach column $net_route_columns($net) {
            set distance [expr {abs($preferred-$column)}]
            if {$distance < $best_distance} {
                set best $column
                set best_distance $distance
            }
        }
        if {$best_distance <= 6.0} { return $best }
    }
    for {set radius 0} {$radius < 400} {incr radius} {
        foreach sign {1 -1} {
            if {$radius == 0 && $sign < 0} { continue }
            set candidate [expr {round(($preferred+$sign*0.8*$radius)*10.0)/10.0}]
            if {$candidate < -90.0 || $candidate > 90.0} { continue }
            set available 1
            foreach occupied $used_route_columns {
                if {abs($candidate-$occupied) < 0.79} {
                    set available 0
                    break
                }
            }
            if {$available} {
                lappend used_route_columns $candidate
                lappend net_route_columns($net) $candidate
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

proc manual_gate_top {cx cy width nf} {
    set contact_y [expr {$cy+$width/2.0+0.80}]
    set route_y [expr {$cy+$width/2.0+0.70}]
    foreach xoff [gate_offsets $nf] {
        set x [expr {$cx+$xoff}]
        paint_rect polysilicon [expr {$x-0.20}] [expr {$cy+$width/2.0+0.10}] \
            [expr {$x+0.20}] [expr {$contact_y+0.180}]
        paint_rect polycontact [expr {$x-0.115}] [expr {$contact_y-0.115}] \
            [expr {$x+0.115}] [expr {$contact_y+0.115}]
        paint_rect metal1 [expr {$x-0.30}] [expr {$route_y-0.30}] \
            [expr {$x+0.30}] [expr {$route_y+0.30}]
    }
    return $route_y
}

array set tracks {
    VSS -30.0
    EVEN_D -15.0 EVEN_DB -13.6 ODD_D -12.2 ODD_DB -10.8
    EVEN_CAPTURE_CLK -9.4 ODD_CAPTURE_CLK -2.4
    E_SET_TAIL -8.0 E_RST_TAIL -6.6 O_SET_TAIL -5.2 O_RST_TAIL -3.8
    E_QI 10.0 E_QBI 11.4 O_QI 12.8 O_QBI 14.2
    E_QBBUF 15.6 E_QBUF 17.0 O_QBBUF 18.4 O_QBUF 19.8
    EVEN_Q 23.0 EVEN_QB 24.4 ODD_Q 25.8 ODD_QB 27.2
    EVEN_CAPTURE_CLKB 30.0
    E_PSET_TAIL 32.0 E_PRST_TAIL 33.4 O_PSET_TAIL 34.8 O_PRST_TAIL 36.2
    EVEN_D_BUF 38.0 EVEN_DB_BUF 39.4 ODD_D_BUF 40.8 ODD_DB_BUF 42.2
    ODD_CAPTURE_CLKB 43.6
    VDD 85.0
}
array set net_min {}
array set net_max {}

proc connect_net {net x y} {
    global tracks net_min net_max
    set ty $tracks($net)
    set half_width 0.23
    set landing_half [expr {$net eq "VDD" || $net eq "VSS" ? 0.38 : 0.23}]
    paint_rect metal3 [expr {$x-$half_width}] [expr {min($y,$ty)-0.38}] \
        [expr {$x+$half_width}] [expr {max($y,$ty)+0.38}]
    # Via3 needs a legal Metal3 landing.  Keep the long access wire narrow,
    # but widen only at the M3/M4 transition instead of widening the full run.
    paint_rect metal3 [expr {$x-0.23}] [expr {$ty-0.23}] \
        [expr {$x+0.23}] [expr {$ty+0.23}]
    paint_rect metal4 [expr {$x-$landing_half}] [expr {$ty-$landing_half}] \
        [expr {$x+$landing_half}] [expr {$ty+$landing_half}]
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

# instance kind width fingers x y drain gate source.  Even and odd lanes are
# mirrored about x=0; state nodes and write tails remain local to each lane.
set devices {
    {XEDN nfet_03v3 8 4 -66 5 EVEN_D_BUF EVEN_DB VSS}
    {XEDBN nfet_03v3 8 4 -54 5 EVEN_DB_BUF EVEN_D VSS}
    {XODBN nfet_03v3 8 4 54 5 ODD_DB_BUF ODD_D VSS}
    {XODN nfet_03v3 8 4 66 5 ODD_D_BUF ODD_DB VSS}

    {XELQN nfet_03v3 8 2 -42 10 E_QI E_QBI VSS}
    {XELBN nfet_03v3 8 2 -30 10 E_QBI E_QI VSS}
    {XESETD nfet_03v3 8 4 -30 -5 E_QBI EVEN_D_BUF E_SET_TAIL}
    {XESETC nfet_03v3 8 8 -42 -5 E_SET_TAIL EVEN_CAPTURE_CLK VSS}
    {XERSTD nfet_03v3 8 4 -42 -17 E_QI EVEN_DB_BUF E_RST_TAIL}
    {XERSTC nfet_03v3 8 8 -30 -17 E_RST_TAIL EVEN_CAPTURE_CLK VSS}
    {XEQBN nfet_03v3 4 2 -66 22 E_QBBUF E_QI VSS}
    {XEQON nfet_03v3 8 3 -78 22 EVEN_Q E_QBBUF VSS}
    {XEBBN nfet_03v3 4 2 -12 22 E_QBUF E_QBI VSS}
    {XEBON nfet_03v3 8 3 -24 22 EVEN_QB E_QBUF VSS}

    {XOLQN nfet_03v3 8 2 42 10 O_QI O_QBI VSS}
    {XOLBN nfet_03v3 8 2 30 10 O_QBI O_QI VSS}
    {XOSETD nfet_03v3 8 4 30 -5 O_QBI ODD_D_BUF O_SET_TAIL}
    {XOSETC nfet_03v3 8 8 42 -5 O_SET_TAIL ODD_CAPTURE_CLK VSS}
    {XORSTD nfet_03v3 8 4 42 -17 O_QI ODD_DB_BUF O_RST_TAIL}
    {XORSTC nfet_03v3 8 8 30 -17 O_RST_TAIL ODD_CAPTURE_CLK VSS}
    {XOQBN nfet_03v3 4 2 66 22 O_QBBUF O_QI VSS}
    {XOQON nfet_03v3 8 3 78 22 ODD_Q O_QBBUF VSS}
    {XOBBN nfet_03v3 4 2 12 22 O_QBUF O_QBI VSS}
    {XOBON nfet_03v3 8 3 24 22 ODD_QB O_QBUF VSS}

    {XEDP pfet_03v3 8 8 -66 35 EVEN_D_BUF EVEN_DB VDD}
    {XEDBP pfet_03v3 8 8 -54 35 EVEN_DB_BUF EVEN_D VDD}
    {XODBP pfet_03v3 8 8 54 35 ODD_DB_BUF ODD_D VDD}
    {XODP pfet_03v3 8 8 66 35 ODD_D_BUF ODD_DB VDD}

    {XELQP pfet_03v3 8 2 -42 35 E_QI E_QBI VDD}
    {XELBP pfet_03v3 8 2 -30 35 E_QBI E_QI VDD}
    {XESETPD pfet_03v3 8 4 -42 50 E_QI EVEN_DB_BUF E_PSET_TAIL}
    {XESETPC pfet_03v3 8 8 -30 50 E_PSET_TAIL EVEN_CAPTURE_CLKB VDD}
    {XERSTPD pfet_03v3 8 4 -42 76 E_QBI EVEN_D_BUF E_PRST_TAIL}
    {XERSTPC pfet_03v3 8 8 -30 76 E_PRST_TAIL EVEN_CAPTURE_CLKB VDD}
    {XEQBP pfet_03v3 8 2 -66 50 E_QBBUF E_QI VDD}
    {XEQOP pfet_03v3 8 4 -78 66 EVEN_Q E_QBBUF VDD}
    {XEBBP pfet_03v3 8 2 -12 50 E_QBUF E_QBI VDD}
    {XEBOP pfet_03v3 8 4 -24 66 EVEN_QB E_QBUF VDD}

    {XOLQP pfet_03v3 8 2 42 35 O_QI O_QBI VDD}
    {XOLBP pfet_03v3 8 2 30 35 O_QBI O_QI VDD}
    {XOSETPD pfet_03v3 8 4 42 50 O_QI ODD_DB_BUF O_PSET_TAIL}
    {XOSETPC pfet_03v3 8 8 30 50 O_PSET_TAIL ODD_CAPTURE_CLKB VDD}
    {XORSTPD pfet_03v3 8 4 42 76 O_QBI ODD_D_BUF O_PRST_TAIL}
    {XORSTPC pfet_03v3 8 8 30 76 O_PRST_TAIL ODD_CAPTURE_CLKB VDD}
    {XOQBP pfet_03v3 8 2 66 50 O_QBBUF O_QI VDD}
    {XOQOP pfet_03v3 8 4 78 66 ODD_Q O_QBBUF VDD}
    {XOBBP pfet_03v3 8 2 12 50 O_QBUF O_QBI VDD}
    {XOBOP pfet_03v3 8 4 24 66 ODD_QB O_QBUF VDD}
}

crashbackups stop
load deserializer_split_capture
units microns
paint_rect pwell -95 -32 95 29
paint_rect nwell -95 30 95 90

foreach spec $devices {
    lassign $spec instance kind width nf cx cy drain gate source
    draw_shared_mos $kind $width $nf $cx $cy
}

foreach spec $devices {
    lassign $spec instance kind width nf cx cy drain gate source
    set drain_points {}
    set source_points {}
    set gate_points {}
    set dual_gate 0
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
        if {$dual_gate} {
            set top_gate_y [manual_gate_top $gx $cy $width $group_nf]
        }
        foreach xoff [gate_offsets $group_nf] {
            lappend gate_points [expr {$gx+$xoff}]
        }
    }

    set drain_y [expr {$cy+$yoff}]
    set source_y [expr {$cy-$yoff}]
    set gate_y [expr {$cy-$width/2.0-0.70}]
    set drain_route [route_column [expr {$cx-0.8}] $drain]
    set source_route [route_column [expr {$cx+0.8}] $source]
    set gate_route [route_column $cx $gate]
    set source_routes [list $source_route]
    if {[info exists ::env(LAYOUT_ROUTE_DEBUG)]} {
        puts "ROUTE $instance d=$drain:$drain_route g=$gate:$gate_route s=$source:$source_route"
    }
    if {($source eq "VDD" || $source eq "VSS") && $nf >= 8} {
        lappend source_routes [route_column [expr {$cx+2.4}] $source 1]
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
    if {$dual_gate} {
        paint_rect metal1 [expr {min($gate_route,[lindex $gate_points 0])-0.35}] \
            [expr {$top_gate_y-0.30}] \
            [expr {max($gate_route,[lindex $gate_points end])+0.35}] \
            [expr {$top_gate_y+0.30}]
        stack_to $gate_route $top_gate_y 3
        paint_rect metal3 [expr {$gate_route-0.23}] [expr {$gate_y-0.23}] \
            [expr {$gate_route+0.23}] [expr {$top_gate_y+0.23}]
    }
    connect_net $gate $gate_route $gate_y
}

# Local body-tap columns keep every device inside the latch-up distance rule
# without placing a conducting low-metal strap across signal escape routes.
set p_tap_left -12
set p_tap_right 12
foreach x [list $p_tap_left $p_tap_right] {
    paint_rect psubdiff [expr {$x-0.32}] -17.37 [expr {$x+0.32}] -16.63
    substrate_contact $x -17
    stack_to $x -17 5
}
paint_rect metal5 [expr {$p_tap_left-0.38}] -17.38 83.38 -16.62
paint_rect metal5 82.62 -30.0 83.38 -16.62

# Distributed n-well contacts join VDD on M5.  Their M3 columns have explicit
# route-allocation keepouts, so signal escapes cannot touch the tap stacks.
set nwell_tap_columns {-84 -60 -36 -12 12 36 60 84}
foreach x $nwell_tap_columns {
    foreach y {44 55 67 82} {
        paint_rect nsubdiff [expr {$x-0.32}] [expr {$y-0.37}] \
            [expr {$x+0.32}] [expr {$y+0.37}]
        nwell_contact $x $y
        stack_to $x $y 3
    }
    paint_rect metal3 [expr {$x-0.23}] 43.77 [expr {$x+0.23}] 82.23
    stack_to $x 82 5
}
paint_rect metal5 -87.38 81.62 \
    [expr {[lindex $nwell_tap_columns end]+0.38}] 82.38
paint_rect metal5 -83.38 81.62 -82.62 88.85

# External pins participate in the same compact M4 net buses.
foreach {name number x} {EVEN_D 1 -93 EVEN_DB 2 -91 ODD_D 3 91 ODD_DB 4 93 EVEN_CAPTURE_CLK 5 -89 EVEN_CAPTURE_CLKB 6 -88 ODD_CAPTURE_CLK 7 88 ODD_CAPTURE_CLKB 8 89 EVEN_Q 11 -87 EVEN_QB 12 -85 ODD_Q 13 85 ODD_QB 14 87} {
    connect_net $name $x $tracks($name)
    via_at via4 $x $tracks($name)
    make_port $name $number metal5 [expr {$x-0.45}] [expr {$tracks($name)-0.45}] \
        [expr {$x+0.45}] [expr {$tracks($name)+0.45}]
}
foreach {name number x} {VDD 9 -83 VSS 10 83} {
    connect_net $name $x $tracks($name)
    via_at via4 $x $tracks($name)
    make_port $name $number metal5 [expr {$x-0.55}] [expr {$tracks($name)-0.55}] \
        [expr {$x+0.55}] [expr {$tracks($name)+0.55}]
}

foreach net [array names net_min] {
    set y $tracks($net)
    set bus_half [expr {$net eq "VDD" || $net eq "VSS" ? 0.38 : 0.23}]
    paint_rect metal4 [expr {$net_min($net)-0.38}] [expr {$y-$bus_half}] \
        [expr {$net_max($net)+0.38}] [expr {$y+$bus_half}]
    box values [expr {$net_min($net)-0.20}] [expr {$y-0.20}] \
        [expr {$net_min($net)+0.20}] [expr {$y+0.20}]
    label $net FreeSans 0.30 0 0 0 c metal4
}

# Contact the common PMOS well frequently and tie it to the VDD port on M5.
paint_rect nsubdiff -93 87.95 93 88.85
paint_rect metal1 -93 87.95 93 88.85
foreach x {-90 -80 -70 -60 -50 -40 -30 -20 -10 0 10 20 30 40 50 60 70 80 90} {
    nwell_contact $x 88.4
    stack_to $x 88.4 5
}
paint_rect metal5 -93 87.95 93 88.85
paint_rect metal5 -83.38 85.0 -82.62 88.85

# A contacted substrate guard ring provides explicit body and VSS return.
paint_rect psubdiff -95 -32 -94.2 29
paint_rect psubdiff 94.2 -32 95 29
paint_rect psubdiff -95 -32 95 -31.2
paint_rect psubdiff -95 28.2 95 29
paint_rect metal1 -95 -32 -94.2 29
paint_rect metal1 94.2 -32 95 29
paint_rect metal1 -95 -32 95 -31.2
paint_rect metal1 -95 28.2 95 29
foreach x {-90 -80 -70 -60 -50 -40 -30 -20 -10 0 10 20 30 40 50 60 70 80 90} {
    substrate_contact $x -31.6
    substrate_contact $x 28.6
}
foreach y {-28 -18 -8 2 12 22 27} {
    substrate_contact -94.6 $y
    substrate_contact 94.6 $y
}
stack_to 94.6 -31.6 5
paint_rect metal5 83.0 -31.98 94.98 -31.22
paint_rect metal5 82.62 -31.6 83.38 -30.0

save /work/deserializer_split_capture
gds write /work/deserializer_split_capture.gds
quit -noprompt
