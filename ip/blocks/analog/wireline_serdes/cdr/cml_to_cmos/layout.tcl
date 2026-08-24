# SPDX-License-Identifier: Apache-2.0
# Symmetric held CML-to-CMOS retimer layout for GF180MCU.

set fast_converter [info exists ::env(CML_TO_CMOS_FAST_LAYOUT)]

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
set route_pitch 0.8
set used_route_columns {
    -84.8 -84 -83.2 -60.8 -60 -59.2 -36.8 -36 -35.2
    -21.8 -21 -20.2 -12.8 -12 -11.2 -0.8 0 0.8
    11.2 12 12.8 20.2 21 21.8 35.2 36 36.8
    -56.8 59.2 60 60.8 63.2 83.2 84 84.8
}
if {$fast_converter} {
    # One-micron escape pitch gives the large one-finger SR-stack devices
    # enough diagonal clearance between their M3 gate and diffusion landings.
    set route_pitch 1.0
    set used_route_columns {
        -85.2 -84 -82.8 -61.2 -60 -58.8 -37.2 -36 -34.8
        -13.2 -12 -10.8 10.8 12 13.2 34.8 36 37.2
        58.8 60 61.2 82.8 84 85.2
    }
}
array set net_route_columns {}
array set gate_route_columns {}
set route_occupancies {}
proc route_column {preferred net {force_new 0}} {
    global used_route_columns net_route_columns route_pitch
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
            set candidate [expr {round(($preferred+$sign*$route_pitch*$radius)*10.0)/10.0}]
            if {$candidate < -90.0 || $candidate > 90.0} { continue }
            set available 1
            foreach occupied $used_route_columns {
                if {abs($candidate-$occupied) < $route_pitch-0.01} {
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

proc route_column_at {preferred net y {force_new 0} {extent_y ""}
                      {reuse_gate 0}} {
    global fast_converter tracks used_route_columns net_route_columns
    global gate_route_columns route_occupancies route_pitch
    if {!$fast_converter} { return [route_column $preferred $net $force_new] }

    if {$extent_y eq ""} { set extent_y $y }
    set ymin [expr {min($y,$extent_y,$tracks($net))-0.5}]
    set ymax [expr {max($y,$extent_y,$tracks($net))+0.5}]
    if {$reuse_gate && [info exists gate_route_columns($net)]} {
        set candidate $gate_route_columns($net)
        lappend route_occupancies [list $candidate $ymin $ymax $net]
        return $candidate
    }
    for {set radius 0} {$radius < 400} {incr radius} {
        foreach sign {1 -1} {
            if {$radius == 0 && $sign < 0} { continue }
            set candidate [expr {
                round(($preferred+$sign*$route_pitch*$radius)*10.0)/10.0}]
            if {$candidate < -90.0 || $candidate > 90.0} { continue }
            set available 1
            foreach occupied $used_route_columns {
                if {abs($candidate-$occupied) < $route_pitch-0.01} {
                    set available 0
                    break
                }
            }
            if {!$available} { continue }
            foreach occupancy $route_occupancies {
                lassign $occupancy column other_min other_max other_net
                if {abs($candidate-$column) < $route_pitch-0.01
                        && $ymin < $other_max && $ymax > $other_min} {
                    set available 0
                    break
                }
            }
            if {$available} {
                lappend net_route_columns($net) $candidate
                lappend route_occupancies \
                    [list $candidate $ymin $ymax $net]
                if {$reuse_gate} { set gate_route_columns($net) $candidate }
                return $candidate
            }
        }
    }
    error "No legal interval-aware M3 access column near $preferred"
}

proc claim_route_column {column net y {extent_y ""}} {
    global tracks net_route_columns route_occupancies
    if {$extent_y eq ""} { set extent_y $y }
    lappend net_route_columns($net) $column
    lappend route_occupancies [list $column \
        [expr {min($y,$extent_y,$tracks($net))-0.5}] \
        [expr {max($y,$extent_y,$tracks($net))+0.5}] $net]
    return $column
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

if {$fast_converter} {
    # Preserve the old macro's external pin tracks for drop-in parent
    # replacement. Internal state tracks are kept adjacent in differential
    # pairs and away from the output buses.
    array set tracks {
        VSS -30.0 INP -15.0 INN -13.6 SENSE_CLK -12.2
        SENSE_BOOST_CLK -10.8 NTAIL -8.0 NIP -5.2 NIN -3.8
        DP 14.0 DN 15.4 H 19.6 HB 21.0
        XP 25.2 XN 26.6 OUTP 30.8 OUTN 32.2
        CAPTURE_CLK 34.0 CAPTURE_CLKB 35.4
        REGEN_CLK 38.0 REGEN_CLKB 39.4 VDD 85.0
    }
} else {
    array set tracks {
        VSS -30.0 INP -15.0 INN -13.6 SENSE_CLK -12.2 SENSE_BOOST_CLK -10.8
        NTAIL -8.0 SA -5.2 SB -3.8 NREGEN 10.0
        SXP 14.0 SXN 15.4
        XP 25.2 XN 26.6 BP 28.0 BN 29.4 OUTP 30.8 OUTN 32.2
        CAPTURE_CLK 34.0 CAPTURE_CLKB 35.4
        REGEN_CLK 38.0 REGEN_CLKB 39.4
        VREGP 55.0 VREGN 56.4 VDD 85.0
    }
}
array set net_min {}
array set net_max {}

proc connect_net {net x y} {
    global tracks net_min net_max fast_converter
    set ty $tracks($net)
    # The fast cell's one-micron escape grid can carry full via-landing-width
    # M3 trunks.  Avoid narrow-stem reentrant notches at the M3/M4 landing.
    set half_width [expr {$fast_converter || $net eq "VDD" || $net eq "VSS"
        ? 0.23 : 0.14}]
    set landing_half [expr {$net eq "VDD" || $net eq "VSS" ? 0.38 : 0.23}]
    paint_rect metal3 [expr {$x-$half_width}] [expr {min($y,$ty)-0.38}] \
        [expr {$x+$half_width}] [expr {max($y,$ty)+0.38}]
    if {$fast_converter && abs($y-$ty) < 0.8} {
        # Merge nearby terminal and track via landings without a narrow M3
        # neck that would create two sub-rule re-entrant notches.
        paint_rect metal3 [expr {$x-0.23}] [expr {min($y,$ty)-0.23}] \
            [expr {$x+0.23}] [expr {max($y,$ty)+0.23}]
    }
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

# instance kind width fingers x y drain gate source
if {$fast_converter} {
# The high-current reset bank occupies the lowest available PMOS row because
# the exact-PEX reset interval is only 230 ps.
set devices {
    {XTAIL nfet_03v3 10 5 -2 -12 NTAIL SENSE_CLK VSS}
    {XRNP nfet_03v3 8 12 -25 8 XP XN NIP}
    {XIP nfet_03v3 8 8 -8 8 NIP INP NTAIL}
    {XIN nfet_03v3 8 8 8 8 NIN INN NTAIL}
    {XRNN nfet_03v3 8 12 25 8 XN XP NIN}

    {XOPN nfet_03v3 8 4 -68 20 OUTP H VSS}
    {XND nfet_03v3 8 2 -34 20 DP XP VSS}
    {XNN nfet_03v3 8 2 34 20 DN XN VSS}
    {XONN nfet_03v3 8 4 68 20 OUTN HB VSS}

    {XOPP pfet_03v3 8 3 -68 37 OUTP H VDD}
    {XPD pfet_03v3 8 4 -34 37 DP XP VDD}
    {XRPP pfet_03v3 8 2 -10 61 XP XN VDD}
    {XRPN pfet_03v3 8 2 10 61 XN XP VDD}
    {XHUP pfet_03v3 8 4 -28 61 H XN VDD}
    {XBUP pfet_03v3 8 4 28 61 HB XP VDD}
    {XPN pfet_03v3 8 4 34 37 DN XN VDD}
    {XONP pfet_03v3 8 3 68 37 OUTN HB VDD}

    {XPREP pfet_03v3 8 10 -36 49 XP SENSE_CLK VDD}
    {XPREIP pfet_03v3 8 4 -18 49 NIP SENSE_CLK VDD}
    {XEQUAL pfet_03v3 8 8 0 49 XP SENSE_CLK XN}
    {XPREIN pfet_03v3 8 4 18 49 NIN SENSE_CLK VDD}
    {XPREN pfet_03v3 8 10 36 49 XN SENSE_CLK VDD}

    {XHNR nfet_03v3 8 8 -50 20 H DP VSS}
    {XHNF nfet_03v3 8 1 -42 20 H HB VSS}
    {XBNF nfet_03v3 8 1 42 20 HB H VSS}
    {XBNR nfet_03v3 8 8 50 20 HB DN VSS}
    {XHPF pfet_03v3 8 4 -44 37 H HB VDD}
    {XBPF pfet_03v3 8 4 44 37 HB H VDD}

    {XTAILBOOST nfet_03v3 10 24 30 -12 NTAIL SENSE_BOOST_CLK VSS}
}
} else {
set devices {
    {XACQP nfet_03v3 8 8 -30 8 XP SB NREGEN}
    {XREGENP nfet_03v3 8 3 -21 8 XP XN NREGEN}
    {XIP nfet_03v3 8 2 -15 8 SA INP NTAIL}
    {XRTAIL nfet_03v3 8 8 -6 8 NREGEN REGEN_CLK VSS}
    {XTAILBOOST nfet_03v3 8 6 -6 -6 NTAIL SENSE_BOOST_CLK VSS}
    {XTAIL nfet_03v3 8 2 6 -6 NTAIL SENSE_CLK VSS}
    {XIN nfet_03v3 8 2 15 8 SB INN NTAIL}
    {XREGENN nfet_03v3 8 3 21 8 XN XP NREGEN}
    {XACQN nfet_03v3 8 8 30 8 XN SA NREGEN}

    {XHP pfet_03v3 8 8 -24 74 VREGP REGEN_CLKB VDD}
    {XHN pfet_03v3 8 8 24 74 VREGN REGEN_CLKB VDD}
    {XXPREP  pfet_03v3 8 8 -12 61 XP REGEN_CLK VDD}
    {XXEQUAL pfet_03v3 8 8   0 61 XP REGEN_CLK XN}
    {XXPREN  pfet_03v3 8 8  12 61 XN REGEN_CLK VDD}
    {XALOADP pfet_03v3 8 1  -6 74 SA VSS VDD}
    {XPREP  pfet_03v3 8 2 -12 37 SA SENSE_CLK VDD}
    {XEQUAL pfet_03v3 8 2   0 37 SA SENSE_CLK SB}
    {XPREN  pfet_03v3 8 2  12 37 SB SENSE_CLK VDD}
    {XALOADN pfet_03v3 8 1   6 74 SB VSS VDD}
    {XLATP pfet_03v3 8 8 -18 49 XP XN VREGP}
    {XLATN pfet_03v3 8 8 18 49 XN XP VREGN}
    {XRPREP pfet_03v3 8 2 -30 49 NREGEN REGEN_CLK VDD}
    {XRPREN pfet_03v3 8 2 30 49 NREGEN REGEN_CLK VDD}

    {XPBP pfet_03v3 8 2 -69 37 BP SXP VDD}
    {XPBN nfet_03v3 8 8 -69 14 BP SXP VSS}
    {XOPP pfet_03v3 8 8 -78 37 OUTP BP VDD}
    {XOPN nfet_03v3 8 6 -81 14 OUTP BP VSS}
    {XBP pfet_03v3 8 8 -27 37 SXP XP VDD}
    {XBN nfet_03v3 8 4 -27 22 SXP XP VSS}
    {XDP pfet_03v3 8 8 27 37 SXN XN VDD}
    {XDN nfet_03v3 8 4 27 22 SXN XN VSS}
    {XNBP pfet_03v3 8 2 69 37 BN SXN VDD}
    {XNBN nfet_03v3 8 8 69 14 BN SXN VSS}
    {XONP pfet_03v3 8 8 78 37 OUTN BN VDD}
    {XONN nfet_03v3 8 6 81 14 OUTN BN VSS}
}
}

crashbackups stop
load cml_to_cmos
units microns
paint_rect pwell -95 -70 95 29
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
    if {$fast_converter} {
        set dual_gate [expr {$nf >= 8}]
    } else {
        set dual_gate [expr {[lsearch -exact {
            XACQP XACQN XHP XHN XXPREP XXPREN XXEQUAL XLATP XLATN
        } $instance] >= 0}]
    }
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
    set drain_preferred [expr {$cx-0.8}]
    if {$fast_converter && $instance eq "XPREIP"} {
        # Keep the NIP precharge escape clear of the equalizer's center
        # diffusion landing; the generic nearest-column search otherwise
        # leaves a sub-rule M2 notch between the two same-row devices.
        set drain_preferred -18.8
    }
    if {$fast_converter && $instance eq "XPREIP"} {
        set drain_route [claim_route_column $drain_preferred $drain $drain_y]
    } else {
        set drain_route [route_column_at $drain_preferred $drain $drain_y]
    }
    set local_reset_supply [expr {$instance eq "XRPREP" || $instance eq "XRPREN"}]
    set source_route [route_column_at [expr {$cx+0.8}] $source $source_y \
        $local_reset_supply]
    # Never share a local M1 gate landing between devices.  All copies of a
    # clock meet on their named M4 bus after independent M3 escapes.
    set reuse_gate 0
    set gate_extent [expr {$dual_gate ? $top_gate_y : $gate_y}]
    if {$fast_converter && $instance eq "XNN"} {
        # Keep the local-restorer gate strap clear of the adjacent capture
        # device now that both sit in the compact NMOS row.
        set gate_route [claim_route_column 31.0 $gate $gate_y $gate_extent]
    } else {
        set gate_route [route_column_at $cx $gate $gate_y 0 \
            $gate_extent $reuse_gate]
    }
    set source_routes [list $source_route]
    if {[info exists ::env(LAYOUT_ROUTE_DEBUG)]} {
        puts "ROUTE $instance d=$drain:$drain_route g=$gate:$gate_route s=$source:$source_route"
    }
    if {($source eq "VDD" || $source eq "VSS") && $nf >= 8} {
        lappend source_routes \
            [route_column_at [expr {$cx+2.4}] $source $source_y 1]
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
paint_rect metal5 [expr {$p_tap_left-0.38}] -17.38 85.38 -16.62
paint_rect metal5 84.62 -30.0 85.38 -16.62

# Distributed n-well contacts join VDD on M5.  Their M3 columns have explicit
# route-allocation keepouts, so signal escapes cannot touch the tap stacks.
set nwell_tap_columns {-84 -60 -36 -12 12 36 60 84}
set nwell_tap_rows {44 55 67 82}
if {$fast_converter} {
    # The fast cell uses PMOS rows at y=37, 49, and 67 um. Put the well taps
    # in the open gaps rather than through the wide SR-latch and precharge
    # arrays.
    set nwell_tap_rows {43 55 68 82}
}
foreach x $nwell_tap_columns {
    foreach y $nwell_tap_rows {
        paint_rect nsubdiff [expr {$x-0.32}] [expr {$y-0.37}] \
            [expr {$x+0.32}] [expr {$y+0.37}]
        nwell_contact $x $y
        stack_to $x $y 3
    }
    paint_rect metal3 [expr {$x-0.23}] \
        [expr {[lindex $nwell_tap_rows 0]-0.23}] \
        [expr {$x+0.23}] 82.23
    stack_to $x 82 5
}
paint_rect metal5 -87.38 81.62 \
    [expr {[lindex $nwell_tap_columns end]+0.38}] 82.38
paint_rect metal5 -87.38 81.62 -86.62 88.85

# External pins participate in the same compact M4 net buses.
foreach {name number x} {INP 1 -93 INN 2 -91 SENSE_CLK 3 -89 REGEN_CLK 4 87 REGEN_CLKB 5 89 CAPTURE_CLK 6 91 CAPTURE_CLKB 7 93 OUTP 10 -89 OUTN 11 89 SENSE_BOOST_CLK 12 -87} {
    connect_net $name $x $tracks($name)
    via_at via4 $x $tracks($name)
    make_port $name $number metal5 [expr {$x-0.45}] [expr {$tracks($name)-0.45}] \
        [expr {$x+0.45}] [expr {$tracks($name)+0.45}]
}
foreach {name number x} {VDD 8 -87 VSS 9 85} {
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

if {$fast_converter} {
    # The converter's left and right output banks must not share a long,
    # sub-micron M4 return to a single edge port.  Parallel full-width M4/M5
    # rails and distributed Via4 landings bound local rail bounce in exact
    # extraction while also giving the symmetric device rows equal supply
    # impedance.  The existing named VDD/VSS buses and ports remain unchanged.
    paint_rect metal4 -90 -30.60 90 -29.40
    paint_rect metal5 -90 -30.60 90 -29.40
    paint_rect metal4 -90 84.40 90 85.60
    paint_rect metal5 -90 84.40 90 85.60
    foreach x {-88 -76 -64 -52 -40 -28 -16 -4 8 20 32 44 56 68 80 88} {
        via_at via4 $x -30.0
        via_at via4 $x 85.0
    }
}

# Contact the common PMOS well frequently and tie it to the VDD port on M5.
paint_rect nsubdiff -93 87.95 93 88.85
paint_rect metal1 -93 87.95 93 88.85
foreach x {-90 -80 -70 -60 -50 -40 -30 -20 -10 0 10 20 30 40 50 60 70 80 90} {
    nwell_contact $x 88.4
    stack_to $x 88.4 5
}
paint_rect metal5 -93 87.95 93 88.85
paint_rect metal5 -87.38 85.0 -86.62 88.85

# A contacted substrate guard ring provides explicit body and VSS return.
paint_rect psubdiff -95 -70 -94.2 29
paint_rect psubdiff 94.2 -70 95 29
paint_rect psubdiff -95 -70 95 -69.2
paint_rect psubdiff -95 28.2 95 29
paint_rect metal1 -95 -70 -94.2 29
paint_rect metal1 94.2 -70 95 29
paint_rect metal1 -95 -70 95 -69.2
paint_rect metal1 -95 28.2 95 29
foreach x {-90 -80 -70 -60 -50 -40 -30 -20 -10 0 10 20 30 40 50 60 70 80 90} {
    substrate_contact $x -69.6
    substrate_contact $x 28.6
}
foreach y {-66 -56 -46 -36 -26 -16 -6 4 14 24 27} {
    substrate_contact -94.6 $y
    substrate_contact 94.6 $y
}
stack_to 94.6 -69.6 5
paint_rect metal5 85.0 -69.98 94.98 -69.22
paint_rect metal5 84.62 -69.6 85.38 -30.0

save /work/cml_to_cmos
gds write /work/cml_to_cmos.gds
quit -noprompt
