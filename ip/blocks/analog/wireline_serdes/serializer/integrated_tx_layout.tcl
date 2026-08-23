# SPDX-License-Identifier: Apache-2.0
# Integrated half-rate serializer and programmable CML TX layout.

proc paint_rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}
proc via_at {layer x y} {
    paint_rect $layer [expr {$x-0.18}] [expr {$y-0.18}] \
        [expr {$x+0.18}] [expr {$y+0.18}]
}
proc via_pair_x {layer x y} {
    foreach xoff {-0.32 0.32} { via_at $layer [expr {$x+$xoff}] $y }
}
proc substrate_contact {x y} {
    paint_rect psubdiffcont [expr {$x-0.25}] [expr {$y-0.30}] \
        [expr {$x+0.25}] [expr {$y+0.30}]
}
proc nwell_contact {x y} {
    paint_rect nsubdiffcont [expr {$x-0.25}] [expr {$y-0.30}] \
        [expr {$x+0.25}] [expr {$y+0.30}]
}
proc make_port {name number layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    label $name FreeSans 0.5 0 0 0 c $layer
    port make $number
}
proc stack_to {x y highest} {
    foreach layer {metal1 metal2} {
        paint_rect $layer [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
    }
    via_at via1 $x $y
    if {$highest >= 3} {
        paint_rect metal3 [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
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
proc stack_from3_to {x y highest} {
    paint_rect metal3 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    if {$highest >= 4} {
        via_at via3 $x $y
        paint_rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
    }
    if {$highest >= 5} {
        via_at via4 $x $y
        paint_rect metal5 [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
    }
}
proc stack_from2_to {x y highest} {
    paint_rect metal2 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    paint_rect metal3 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    via_at via2 $x $y
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
proc mos_terminal_strap {cx cy yoff xs} {
    set y [expr {$cy+$yoff}]
    foreach xoff $xs {
        set x [expr {$cx+$xoff}]
        paint_rect metal1 [expr {$x-0.34}] [expr {$y-0.34}] \
            [expr {$x+0.34}] [expr {$y+0.34}]
        via_at via1 $x $y
    }
    paint_rect metal2 [expr {$cx+[lindex $xs 0]-0.38}] [expr {$y-0.38}] \
        [expr {$cx+[lindex $xs end]+0.38}] [expr {$y+0.38}]
}
proc manual_gate {cx y half_width xs} {
    paint_rect polysilicon [expr {$cx-$half_width}] $y \
        [expr {$cx+$half_width}] [expr {$y+0.25}]
    foreach xoff $xs {
        set x [expr {$cx+$xoff}]
        paint_rect polysilicon [expr {$x-0.20}] $y \
            [expr {$x+0.20}] [expr {$y+0.90}]
        paint_rect polycontact [expr {$x-0.115}] [expr {$y+0.585}] \
            [expr {$x+0.115}] [expr {$y+0.815}]
    }
    paint_rect metal1 [expr {$cx+[lindex $xs 0]-0.35}] [expr {$y+0.40}] \
        [expr {$cx+[lindex $xs end]+0.35}] [expr {$y+1.00}]
}
proc manual_gate_bottom {cx y half_width xs} {
    paint_rect polysilicon [expr {$cx-$half_width}] $y \
        [expr {$cx+$half_width}] [expr {$y+0.25}]
    foreach xoff $xs {
        set x [expr {$cx+$xoff}]
        paint_rect polysilicon [expr {$x-0.20}] [expr {$y-0.65}] \
            [expr {$x+0.20}] [expr {$y+0.25}]
        paint_rect polycontact [expr {$x-0.115}] [expr {$y-0.565}] \
            [expr {$x+0.115}] [expr {$y-0.335}]
    }
    paint_rect metal1 [expr {$cx+[lindex $xs 0]-0.35}] [expr {$y-0.65}] \
        [expr {$cx+[lindex $xs end]+0.35}] [expr {$y-0.05}]
}

crashbackups stop
set serializer_cell serializer_tx
set tail_length 0.5
set boost_loads 0
if {[info exists ::env(SERIALIZER_TX_CELL)]} {
    set serializer_cell $::env(SERIALIZER_TX_CELL)
}
if {[info exists ::env(SERIALIZER_TX_TAIL_LENGTH)]} {
    set tail_length $::env(SERIALIZER_TX_TAIL_LENGTH)
}
if {[info exists ::env(SERIALIZER_TX_BOOST_LOADS)]} {
    set boost_loads $::env(SERIALIZER_TX_BOOST_LOADS)
}
load ${serializer_cell}_hier
set data_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 20 l 0.28 nf 5 guard 0 topc 0 botc 0 full_metal 0]
set select_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 20 l 0.28 nf 5 guard 0 topc 0 botc 0 full_metal 0]
set tail_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 20 l $tail_length nf 14 guard 0 topc 0 botc 0 full_metal 0]
set base_load_cell [magic::gencell_makecell gf180mcu::ppolyf_u \
    w 1 l 0.8 guard 1 full_metal 1]
set trim_load_cell [magic::gencell_makecell gf180mcu::ppolyf_u \
    w 1 l 0.8 guard 1 full_metal 1]
set load_switch_cell [magic::gencell_makecell gf180mcu::pfet_03v3 \
    w 20 l 0.28 nf 5 guard 0 topc 0 botc 0 full_metal 0]

units microns
if {$boost_loads} {
    set base_load_x 60.0
    set all_load_x {-60.0 -53.6 -47.2 -40.8 -34.4 -28.0 -21.6 -15.2 -8.8 8.8 15.2 21.6 28.0 34.4 40.8 47.2 53.6 60.0}
    set trim_load_x {-53.6 -47.2 -40.8 -34.4 -28.0 -21.6 -15.2 -8.8 8.8 15.2 21.6 28.0 34.4 40.8 47.2 53.6}
    set switch_x $trim_load_x
    set well_contacts {-56.8 -50.4 -44.0 -37.6 -31.4 -24.8 -18.4 -12.0 -5.2 5.2 12.0 18.4 24.8 31.4 37.6 44.0 50.4 56.8}
    set rail_edge 60.8
    set output_edge 60.70
} else {
    set base_load_x 34.4
    set all_load_x {-34.4 -28.0 -21.6 -15.2 -8.8 8.8 15.2 21.6 28.0 34.4}
    set trim_load_x {-28.0 -21.6 -15.2 -8.8 8.8 15.2 21.6 28.0}
    set switch_x $trim_load_x
    set well_contacts {-31.4 -24.8 -18.4 -12.0 -5.2 5.2 12.0 18.4 24.8 31.4}
    set rail_edge 35.2
    set output_edge 35.10
}
set placements [list \
        $data_cell XEVEN_P -15 0 $data_cell XODD_P -5 0 \
        $data_cell XODD_N 5 0 $data_cell XEVEN_N 15 0 \
        $select_cell XSELECT_E -10 -24 $select_cell XSELECT_O 10 -24 \
        $tail_cell XTAIL 0 -48 \
        $base_load_cell XBASE_P [expr {-$base_load_x}] 15.73 \
        $base_load_cell XBASE_N $base_load_x 15.73 \
        $trim_load_cell XTRIM_P0 -8.8 15.73 \
        $trim_load_cell XTRIM_P1 -15.2 15.73 \
        $trim_load_cell XTRIM_P2 -21.6 15.73 \
        $trim_load_cell XTRIM_P3 -28.0 15.73 \
        $trim_load_cell XTRIM_N0 8.8 15.73 \
        $trim_load_cell XTRIM_N1 15.2 15.73 \
        $trim_load_cell XTRIM_N2 21.6 15.73 \
        $trim_load_cell XTRIM_N3 28.0 15.73 \
        $load_switch_cell XSW_P0 -8.8 42 \
        $load_switch_cell XSW_P1 -15.2 42 \
        $load_switch_cell XSW_P2 -21.6 42 \
        $load_switch_cell XSW_P3 -28.0 42 \
        $load_switch_cell XSW_N0 8.8 42 \
        $load_switch_cell XSW_N1 15.2 42 \
        $load_switch_cell XSW_N2 21.6 42 \
        $load_switch_cell XSW_N3 28.0 42]
if {$boost_loads} {
    lappend placements \
        $trim_load_cell XTRIM_P4 -34.4 15.73 \
        $trim_load_cell XTRIM_P5 -40.8 15.73 \
        $trim_load_cell XTRIM_P6 -47.2 15.73 \
        $trim_load_cell XTRIM_P7 -53.6 15.73 \
        $trim_load_cell XTRIM_N4 34.4 15.73 \
        $trim_load_cell XTRIM_N5 40.8 15.73 \
        $trim_load_cell XTRIM_N6 47.2 15.73 \
        $trim_load_cell XTRIM_N7 53.6 15.73 \
        $load_switch_cell XSW_P4 -34.4 42 \
        $load_switch_cell XSW_P5 -40.8 42 \
        $load_switch_cell XSW_P6 -47.2 42 \
        $load_switch_cell XSW_P7 -53.6 42 \
        $load_switch_cell XSW_N4 34.4 42 \
        $load_switch_cell XSW_N5 40.8 42 \
        $load_switch_cell XSW_N6 47.2 42 \
        $load_switch_cell XSW_N7 53.6 42
}
foreach {cell instance x y} $placements {
    getcell $cell child 0 0 parent $x $y
    identify $instance
}
select top cell
flatten $serializer_cell
load $serializer_cell
units microns
if {$boost_loads} {
    paint_rect pwell -64 -63 64 30.5
    paint_rect nwell -58 31 -4.4 54.5
    paint_rect nwell 4.4 31 58 54.5
} else {
    paint_rect pwell -38 -63 38 30.5
    paint_rect nwell -32 31 -4.4 54.5
    paint_rect nwell 4.4 31 32 54.5
}

set five_gates {-1.6 -0.8 0.0 0.8 1.6}
set five_a {-2.0 -0.4 1.2}
set five_b {-1.2 0.4 2.0}
if {$tail_length <= 0.28} {
    set tail_gates {-5.2 -4.4 -3.6 -2.8 -2.0 -1.2 -0.4 0.4 1.2 2.0 2.8 3.6 4.4 5.2}
    set tail_drain_contacts {-5.6 -4.0 -2.4 -0.8 0.8 2.4 4.0 5.6}
    set tail_source_contacts {-4.8 -3.2 -1.6 0.0 1.6 3.2 4.8}
    set tail_drain_vias {-4.0 -0.8 2.4 5.6}
    set tail_source_vias {-4.8 -1.6 1.6 4.8}
    set tail_gate_half_width 5.43
} else {
    set tail_gates {-6.63 -5.61 -4.59 -3.57 -2.55 -1.53 -0.51 0.51 1.53 2.55 3.57 4.59 5.61 6.63}
    set tail_drain_contacts {-7.14 -5.10 -3.06 -1.02 1.02 3.06 5.10 7.14}
    set tail_source_contacts {-6.12 -4.08 -2.04 0.0 2.04 4.08 6.12}
    set tail_drain_vias {-5.10 -1.02 3.06 7.14}
    set tail_source_vias {-6.12 -2.04 2.04 6.12}
    set tail_gate_half_width 6.86
}

# Four matched data banks and two matched clock-selection banks.
foreach x {-15 -5 5 15} {
    manual_gate $x 10.10 1.75 $five_gates
    mos_terminal_strap $x 0 8.0 $five_a
    mos_terminal_strap $x 0 -8.0 $five_b
}
foreach {name number x} [list EVEN_P 1 -15 ODD_P 3 -5 ODD_N 4 5 EVEN_N 2 15] {
    make_port $name $number metal1 [expr {$x-2.0}] 10.50 \
        [expr {$x+2.0}] 11.10
}
foreach x {-10 10} {
    manual_gate $x -13.90 1.75 $five_gates
    mos_terminal_strap $x -24 8.0 $five_a
    mos_terminal_strap $x -24 -8.0 $five_b
}
make_port CLK_P 5 metal1 -12.0 -13.50 -8.0 -12.90
make_port CLK_N 6 metal1 8.0 -13.50 12.0 -12.90

# Data drains connect directly to the two programmable TX output buses.
paint_rect metal3 -17.4 7.50 -2.6 8.50
paint_rect metal3 2.6 7.50 17.4 8.50
foreach x {-15 -5 5 15} {
    foreach xoff $five_a { via_at via2 [expr {$x+$xoff}] 8.0 }
}
paint_rect metal3 -9.70 7.50 -8.30 15.60
paint_rect metal3 8.30 7.50 9.70 15.60

# Equal-centroid EVEN sources use M5; inner ODD sources use M4.
foreach x {-15 15} { stack_from2_to $x -8.0 5 }
paint_rect metal5 -15.38 -8.38 15.38 -7.62
paint_rect metal5 -10.38 -16.0 -9.62 -7.62
stack_from2_to -10 -16.0 5
foreach x {-5 5} { stack_from2_to $x -8.0 4 }
paint_rect metal4 -5.38 -8.38 5.38 -7.62
paint_rect metal4 9.62 -16.0 10.38 -7.62
paint_rect metal4 4.62 -8.38 10.38 -7.62
stack_from2_to 10 -16.0 4

# Selection sources share a short local node over the directly adjacent tail.
foreach x {-10 10} {
    foreach xoff $five_b { stack_to [expr {$x+$xoff}] -32.0 3 }
}
paint_rect metal3 -12.4 -32.6 12.4 -31.4
paint_rect metal3 -0.7 -40.0 0.7 -31.4
mos_terminal_strap 0 -48 8.0 $tail_drain_contacts
mos_terminal_strap 0 -48 -8.0 $tail_source_contacts
foreach x $tail_drain_vias { via_at via2 $x -40.0 }
paint_rect metal3 -7.5 -40.6 7.5 -39.4
manual_gate 0 -37.90 $tail_gate_half_width $tail_gates
make_port VBIAS 7 metal1 -0.4 -37.45 0.4 -36.95

# Load resistors, vertical trim branches, and the shared VDD rail.
foreach x $all_load_x {
    foreach y {15.0 16.46} {
        paint_rect metal1 [expr {$x-0.28}] [expr {$y-0.28}] \
            [expr {$x+0.28}] [expr {$y+0.28}]
        via_at via1 $x $y
        paint_rect metal2 [expr {$x-0.42}] [expr {$y-0.42}] \
            [expr {$x+0.42}] [expr {$y+0.42}]
    }
}
foreach x $trim_load_x {
    via_at via2 $x 16.46
    via_at via2 $x 34.0
    paint_rect metal3 [expr {$x-0.70}] 15.96 [expr {$x+0.70}] 34.50
}
foreach x [list [expr {-$base_load_x}] $base_load_x] {
    via_at via2 $x 16.46
    via_at via2 $x 50.0
    paint_rect metal3 [expr {$x-0.70}] 15.96 [expr {$x+0.70}] 50.50
}
paint_rect metal3 [expr {-$output_edge}] 14.40 -8.30 15.60
paint_rect metal3 8.30 14.40 $output_edge 15.60
foreach x $all_load_x {
    via_at via2 $x 15.0
}
set switch_even {-2.0 -0.4 1.2}
set switch_odd {-1.2 0.4 2.0}
foreach x $switch_x {
    manual_gate $x 52.10 1.75 $five_gates
    mos_terminal_strap $x 42 -8.0 $switch_even
    mos_terminal_strap $x 42 8.0 $switch_odd
}
paint_rect metal2 [expr {-$rail_edge}] 49.40 $rail_edge 50.60
paint_rect metal3 [expr {-$rail_edge}] 49.40 $rail_edge 50.60
foreach x $switch_x {
    via_pair_x via2 $x 50.0
}
foreach x $well_contacts {
    paint_rect nsubdiff [expr {$x-0.35}] 48.60 [expr {$x+0.35}] 49.40
    nwell_contact $x 49.0
    paint_rect metal1 [expr {$x-0.38}] 48.62 [expr {$x+0.38}] 49.38
    paint_rect metal2 [expr {$x-0.42}] 48.58 [expr {$x+0.42}] 49.50
    via_at via1 $x 49.0
}
foreach {idx layer xl xr} {0 metal2 -8.8 8.8 1 metal3 -15.2 15.2 2 metal4 -21.6 21.6 3 metal5 -28.0 28.0} {
    foreach x [list $xl $xr] {
        paint_rect metal1 [expr {$x-0.50}] 52.50 [expr {$x+0.50}] 53.10
        paint_rect metal2 [expr {$x-0.55}] 52.30 [expr {$x+0.55}] 53.10
        via_pair_x via1 $x 52.70
        if {$idx >= 1} { paint_rect metal3 [expr {$x-0.55}] 52.30 [expr {$x+0.55}] 53.10; via_pair_x via2 $x 52.70 }
        if {$idx >= 2} { paint_rect metal4 [expr {$x-0.55}] 52.30 [expr {$x+0.55}] 53.10; via_pair_x via3 $x 52.70 }
        if {$idx >= 3} { paint_rect metal5 [expr {$x-0.55}] 52.30 [expr {$x+0.55}] 53.10; via_pair_x via4 $x 52.70 }
    }
    paint_rect $layer [expr {$xl-0.50}] 52.35 [expr {$xr+0.50}] 53.05
    set label_x [lindex {0 -10 10 -22} $idx]
    make_port LOAD_EN${idx}_N [expr {8+$idx}] $layer \
        [expr {$label_x-0.45}] 52.35 [expr {$label_x+0.45}] 53.05
}
# The top bandwidth code controls three matched branches per side.  Codes
# zero through three retain the base topology; code four closes this extra M5
# gate bus and selects all six trim branches.
if {$boost_loads} {
    foreach x {-53.6 -47.2 -40.8 -34.4 34.4 40.8 47.2 53.6} {
        stack_to $x 52.70 5
    }
    paint_rect metal5 -54.1 52.35 54.1 53.05
}

# Tail return and a dense contacted guard ring around the complete NMOS stack.
paint_rect metal2 -8 -56.6 8 -55.4
paint_rect metal3 -8 -56.6 8 -55.4
foreach x $tail_source_vias { via_at via2 $x -56.0 }
paint_rect psubdiff -23 -62 -22.2 13
paint_rect psubdiff 22.2 -62 23 13
paint_rect psubdiff -23 -62 23 -61.2
paint_rect psubdiff -23 12.2 23 13
paint_rect metal1 -23 -62 -22.2 13
paint_rect metal1 22.2 -62 23 13
paint_rect metal1 -23 -62 23 -61.2
paint_rect metal1 -23 12.2 23 13
foreach x {-20 -16 -12 -8 -4 0 4 8 12 16 20} {
    substrate_contact $x -61.6
    substrate_contact $x 12.6
}
foreach y {-59 -55 -51 -47 -43 -39 -35 -31 -27 -23 -19 -15 -11 -7 -3 1 5 9} {
    substrate_contact -22.6 $y
    substrate_contact 22.6 $y
}
via_at via1 0 -61.6
paint_rect metal2 -0.6 -61.9 0.6 -55.4

make_port VDD 12 metal3 -1 49.45 1 50.55
make_port VSS 13 metal3 -1 -56.55 1 -55.45
make_port OUTP 14 metal3 -9.45 9 -8.55 12
make_port OUTN 15 metal3 8.55 9 9.45 12
save /work/$serializer_cell
gds write /work/$serializer_cell.gds
quit -noprompt
