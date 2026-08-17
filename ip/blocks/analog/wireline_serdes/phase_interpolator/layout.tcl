# SPDX-License-Identifier: Apache-2.0
# Matched GF180 layout for the two-input CML phase interpolator.

proc paint_rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}

proc via_at {layer x y} {
    paint_rect $layer [expr {$x-0.18}] [expr {$y-0.18}] \
        [expr {$x+0.18}] [expr {$y+0.18}]
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

proc substrate_contact {x y} {
    paint_rect psubdiffcont [expr {$x-0.25}] [expr {$y-0.30}] \
        [expr {$x+0.25}] [expr {$y+0.30}]
}

proc make_port {name number layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    label $name FreeSans 0.5 0 0 0 c $layer
    port make $number
}

proc mos_terminal_strap {cx cy yoff xs highest} {
    set y [expr {$cy+$yoff}]
    foreach xoff $xs {
        set x [expr {$cx+$xoff}]
        paint_rect metal1 [expr {$x-0.30}] [expr {$y-0.30}] \
            [expr {$x+0.30}] [expr {$y+0.30}]
        via_at via1 $x $y
        if {$highest >= 3} { via_at via2 $x $y }
    }
    paint_rect metal2 [expr {$cx+[lindex $xs 0]-0.38}] [expr {$y-0.38}] \
        [expr {$cx+[lindex $xs end]+0.38}] [expr {$y+0.38}]
    if {$highest >= 3} {
        paint_rect metal3 [expr {$cx+[lindex $xs 0]-0.38}] [expr {$y-0.38}] \
            [expr {$cx+[lindex $xs end]+0.38}] [expr {$y+0.38}]
    }
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

proc manual_gate_top {cx y half_width xs} {
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

crashbackups stop
load phase_interpolator_hier

set input_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 5 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set weight_tail_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 5 l 0.28 nf 4 guard 0 topc 0 botc 0 full_metal 0]
set buffer_tail_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 10 l 0.28 nf 4 guard 0 topc 0 botc 0 full_metal 0]
set interpolate_load [magic::gencell_makecell gf180mcu::ppolyf_u \
    w 2 l 4.00 guard 1 full_metal 1]
set output_load [magic::gencell_makecell gf180mcu::ppolyf_u \
    w 2 l 5.25 guard 1 full_metal 1]

units microns
foreach {cell instance x y} [list \
        $input_cell XAP -27 0 $input_cell XBP -19 0 \
        $input_cell XBN -11 0 $input_cell XAN -3 0 \
        $weight_tail_cell XTAILA -15 -12 $weight_tail_cell XTAILB -15 -22 \
        $input_cell XBUFP 11 0 $input_cell XBUFN 19 0 \
        $buffer_tail_cell XTAILBUF 15 -12 \
        $interpolate_load XRL1P -23 18 $interpolate_load XRL1N -7 18 \
        $output_load XRL2P 11 18 $output_load XRL2N 19 18] {
    getcell $cell child 0 0 parent $x $y
    identify $instance
}

select top cell
flatten phase_interpolator
load phase_interpolator
units microns
paint_rect pwell -36 -29 29 27

# The A/B input quartet uses a common-centroid AP/BP/BN/AN ordering.
foreach x {-27 -19 -11 -3} {
    mos_terminal_strap $x 0 1.5 {-0.8 0.8} 3
    mos_terminal_strap $x 0 -1.5 {0.0} 2
}
foreach x {11 19} {
    mos_terminal_strap $x 0 1.5 {-0.8 0.8} 3
    mos_terminal_strap $x 0 -1.5 {0.0} 3
}
foreach x {-27 -19 -11 -3} { manual_gate_bottom $x -2.85 0.55 {-0.4 0.4} }
foreach x {11 19} { manual_gate_top $x 2.60 0.55 {-0.4 0.4} }

# Summed first-stage drain nodes and their nearby loads.
paint_rect metal3 -28.2 1.05 -17.8 1.95
paint_rect metal3 -12.2 1.05 -1.8 1.95
paint_rect metal3 -23.45 1.05 -22.55 16.6
paint_rect metal3 -7.45 1.05 -6.55 16.6

# A-tail source rail is on M5; the nested B-tail source rail is on M4.
paint_rect metal5 -28.2 -1.95 -1.8 -1.05
foreach x {-27 -3} { stack_to $x -1.5 5 }
paint_rect metal5 -15.45 -10.5 -14.55 -1.05
paint_rect metal4 -20.2 -1.95 -9.8 -1.05
foreach x {-19 -11} {
    stack_to $x -1.5 4
}
paint_rect metal3 -16.5 -20.95 -12.62 -20.05
paint_rect metal4 -13.45 -20.5 -12.55 -1.05

# Weight-tail devices: drains upward, sources locally to the VSS guard return.
foreach {cy drain_y source_y} [list -12 -10.5 -13.5 -22 -20.5 -23.5] {
    mos_terminal_strap -15 $cy 1.5 {-1.6 0.0 1.6} 3
    mos_terminal_strap -15 $cy -1.5 {-0.8 0.8} 3
    manual_gate_bottom -15 [expr {$cy-2.85}] 1.35 {-1.2 -0.4 0.4 1.2}
    paint_rect metal3 -17.0 [expr {$source_y-0.45}] -13.0 [expr {$source_y+0.45}]
}
paint_rect metal4 -13.38 -20.88 -12.62 -20.12
via_at via3 -13 -20.5
paint_rect metal4 -15.38 -10.88 -14.62 -10.12
paint_rect metal5 -15.38 -10.88 -14.62 -10.12
via_at via3 -15 -10.5
via_at via4 -15 -10.5

# Buffer pair, short shared source node, and directly adjacent tail.
paint_rect metal3 9.8 -1.95 20.2 -1.05
paint_rect metal3 14.55 -10.0 15.45 -1.05
foreach x {11 19} { via_at via2 $x -1.5 }
mos_terminal_strap 15 -12 4.0 {-1.6 0.0 1.6} 3
mos_terminal_strap 15 -12 -4.0 {-0.8 0.8} 3
manual_gate_bottom 15 -17.35 1.35 {-1.2 -0.4 0.4 1.2}
paint_rect metal3 12.6 -16.45 17.4 -15.55

# First-stage nodes drive the buffer gates on different upper metals.
stack_to -23 8.0 5
paint_rect metal5 -23.38 7.62 11.38 8.38
paint_rect metal5 10.62 3.18 11.38 8.38
stack_to 11 3.20 5
stack_to -7 10.0 4
paint_rect metal4 -7.38 9.62 19.38 10.38
paint_rect metal4 18.62 3.18 19.38 10.38
stack_to 19 3.20 4

# Load terminals and VDD bus.
foreach {x roff node_x} [list -23 2.33 -23 -7 2.33 -7 11 2.615 11 19 2.615 19] {
    foreach y [list [expr {18-$roff}] [expr {18+$roff}]] {
        stack_to $x $y 3
    }
    paint_rect metal3 [expr {$x-0.45}] [expr {18+$roff}] [expr {$x+0.45}] 24.8
    stack_to $x 24.4 5
}
paint_rect metal5 -32 24.0 25 24.8
make_port VDD 8 metal5 -5 24.0 -3 24.8

# Output drain trunks are offset outward from the buffer gate stacks.
paint_rect metal3 8.85 1.05 9.95 15.955
paint_rect metal3 20.05 1.05 21.15 15.955
paint_rect metal3 8.85 1.05 12.2 1.95
paint_rect metal3 17.8 1.05 21.15 1.95
paint_rect metal3 8.85 15.505 11.45 16.405
paint_rect metal3 18.55 15.505 21.15 16.405
make_port CLK_P 10 metal3 8.85 13.5 9.95 15.0
make_port CLK_N 11 metal3 20.05 13.5 21.15 15.0

# Four phase inputs route independently on M5 from bottom-edge ports.
foreach {x name number} [list -27 A_P 1 -19 B_P 3 -11 B_N 4 -3 A_N 2] {
    stack_to $x -3.20 5
    paint_rect metal5 [expr {$x-0.38}] -27.0 [expr {$x+0.38}] -2.82
    make_port $name $number metal5 [expr {$x-0.45}] -27.0 [expr {$x+0.45}] -25.8
}

# Tail controls use separate upper-metal tracks and local gate stacks.
stack_to -15 -15.20 4
paint_rect metal4 -34 -15.58 -14.62 -14.82
make_port CTRL_A 5 metal4 -34 -15.58 -32.5 -14.82
stack_to -15 -25.20 4
paint_rect metal4 -15.38 -25.58 27 -24.82
make_port CTRL_B 6 metal4 25.5 -25.58 27 -24.82
stack_to 15 -17.70 4
paint_rect metal4 14.62 -18.08 27 -17.32
make_port VBIAS_BUF 7 metal4 25.5 -18.08 27 -17.32

# Contacted substrate guard and VSS return.
paint_rect psubdiff -36 -29 -35.2 27
paint_rect psubdiff 28.2 -29 29 27
paint_rect psubdiff -36 -29 29 -28.2
paint_rect psubdiff -36 26.2 29 27
paint_rect metal1 -36 -29 -35.2 27
paint_rect metal1 28.2 -29 29 27
paint_rect metal1 -36 -29 29 -28.2
paint_rect metal1 -36 26.2 29 27
foreach x {-33 -27 -21 -15 -9 -3 3 9 15 21 27} {
    substrate_contact $x -28.6
    substrate_contact $x 26.6
}
foreach y {-25 -19 -13 -7 -1 5 11 17 23} {
    substrate_contact -35.6 $y
    substrate_contact 28.6 $y
}
stack_to -35.5 -27.5 5
paint_rect metal5 -35.95 -27.5 -35.05 2.0
make_port VSS 9 metal5 -35.95 -2 -35.05 0

# Local source returns meet the left/right guard without using signal metals.
paint_rect metal3 -35.6 -14.0 -13.0 -13.0
paint_rect metal3 -35.6 -24.0 -13.0 -23.0
paint_rect metal3 12.6 -16.5 28.6 -15.5
foreach {x y} [list -35.6 -13.5 -35.6 -23.5 28.6 -16.0] { stack_to $x $y 3 }

save /work/phase_interpolator
gds write /work/phase_interpolator.gds
quit -noprompt
