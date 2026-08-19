# SPDX-License-Identifier: Apache-2.0
# Matched dual-edge CML sampler layout for the reference-assisted CDR path.

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
load cml_divider_by_2_hier

set signal_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 6 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set clock_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 8 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set tail_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 10 l 0.28 nf 4 guard 0 topc 0 botc 0 full_metal 0]
set reset_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 2 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set load_cell [magic::gencell_makecell gf180mcu::ppolyf_u \
    w 2 l 7.50 guard 1 full_metal 1]

units microns
foreach {cell instance x y} [list \
        $signal_cell XMASTER_XDN -36 4 $signal_cell XMASTER_XLP -28 4 \
        $signal_cell XMASTER_XLN -20 4 $signal_cell XMASTER_XDP -12 4 \
        $clock_cell XMASTER_XCT -30 -8 $clock_cell XMASTER_XCH -18 -8 \
        $tail_cell XMASTER_XTAIL -24 -18 \
        $load_cell XMASTER_XRP -32 20 $load_cell XMASTER_XRN -16 20 \
        $signal_cell XSLAVE_XDN 12 4 $signal_cell XSLAVE_XLP 20 4 \
        $signal_cell XSLAVE_XLN 28 4 $signal_cell XSLAVE_XDP 36 4 \
        $clock_cell XSLAVE_XCT 18 -8 $clock_cell XSLAVE_XCH 30 -8 \
        $tail_cell XSLAVE_XTAIL 24 -18 \
        $load_cell XSLAVE_XRP 16 20 $load_cell XSLAVE_XRN 32 20 \
        $reset_cell XRESET_MASTER -8 -18 \
        $reset_cell XRESET_SLAVE 8 -18] {
    getcell $cell child 0 0 parent $x $y
    identify $instance
}

select top cell
flatten cml_divider_by_2
load cml_divider_by_2
units microns
paint_rect pwell -48 -27 48 28

# Signal quartets use track/hold/hold/track ordering with equal centroids.
foreach x {-36 -28 -20 -12 12 20 28 36} {
    mos_terminal_strap $x 4 1.75 {-0.8 0.8} 3
    mos_terminal_strap $x 4 -1.75 {0.0} 3
}
foreach x {-36 -28 -20 -12 12 20 28 36} {
    manual_gate_bottom $x 0.65 0.55 {-0.4 0.4}
}

# Compact differential output nodes and local resistive loads.
foreach {x1 x2 lx} [list -37.2 -26.8 -32 -21.2 -10.8 -16 \
                           10.8 21.2 16 26.8 37.2 32] {
    paint_rect metal3 $x1 5.30 $x2 6.20
    paint_rect metal3 [expr {$lx-0.45}] 5.30 [expr {$lx+0.45}] 17.25
}

# Track sources use M5 and hold sources use M4 to cross without shorts.
foreach {cx track_l track_r hold_l hold_r track_clk hold_clk} [list \
        -24 -36 -12 -28 -20 -30 -18 \
         24  12  36  20  28  18  30] {
    paint_rect metal5 [expr {$track_l-0.45}] 1.80 [expr {$track_r+0.45}] 2.70
    stack_to $track_l 2.25 5
    stack_to $track_r 2.25 5
    paint_rect metal5 [expr {$track_clk-0.45}] -5.75 [expr {$track_clk+0.45}] 2.70
    stack_from3_to $track_clk -5.75 5

    paint_rect metal4 [expr {min($hold_l,$hold_r,$hold_clk)-0.45}] 1.80 \
        [expr {max($hold_l,$hold_r,$hold_clk)+0.45}] 2.70
    stack_to $hold_l 2.25 4
    stack_to $hold_r 2.25 4
    paint_rect metal4 [expr {$hold_clk-0.45}] -5.75 [expr {$hold_clk+0.45}] 2.70
    stack_from3_to $hold_clk -5.75 4
}

# Clock steering pairs and local tails.
foreach x {-30 -18 18 30} {
    mos_terminal_strap $x -8 2.25 {-0.8 0.8} 3
    mos_terminal_strap $x -8 -2.25 {0.0} 3
    manual_gate_bottom $x -12.35 0.55 {-0.4 0.4}
}
foreach cx {-24 24} {
    paint_rect metal3 [expr {$cx-6.45}] -10.70 [expr {$cx+6.45}] -9.80
    paint_rect metal3 [expr {$cx-0.45}] -14.0 [expr {$cx+0.45}] -9.80
    mos_terminal_strap $cx -18 4.0 {-1.6 0.0 1.6} 3
    mos_terminal_strap $cx -18 -4.0 {-0.8 0.8} 3
    manual_gate_bottom $cx -23.35 1.35 {-1.2 -0.4 0.4 1.2}
    paint_rect metal3 [expr {$cx-2.4}] -22.45 [expr {$cx+2.4}] -21.55
}

# Cross-coupled latch gates enter below the source rails.  Each connection
# changes to M3 in the open channel between devices, then rises to its own
# output node; the two crossing gate branches stay isolated on M4 and M5.
foreach {qp qn xlp xln qn_chan qp_chan} [list \
        -32 -16 -28 -20 -24 -26 \
         16  32  20  28  26  24] {
    stack_to $xlp 0.25 4
    paint_rect metal4 [expr {min($xlp,$qn_chan)-0.38}] -0.13 \
        [expr {max($xlp,$qn_chan)+0.38}] 0.63
    stack_to $qn_chan 0.25 4
    paint_rect metal3 [expr {$qn_chan-0.38}] 0.25 \
        [expr {$qn_chan+0.38}] 5.75
    paint_rect metal3 [expr {min($qn_chan,$qn)-0.38}] 4.70 \
        [expr {max($qn_chan,$qn)+0.38}] 5.58

    stack_to $xln 0.25 5
    paint_rect metal5 [expr {$xln-0.38}] -1.58 \
        [expr {$xln+0.38}] 0.63
    paint_rect metal5 [expr {min($xln,$qp_chan)-0.38}] -1.58 \
        [expr {max($xln,$qp_chan)+0.38}] -0.82
    stack_from3_to $qp_chan -1.20 5
    paint_rect metal3 [expr {$qp_chan-0.38}] -1.20 \
        [expr {$qp_chan+0.38}] 5.75
    paint_rect metal3 [expr {min($qp_chan,$qp)-0.38}] 4.70 \
        [expr {max($qp_chan,$qp)+0.38}] 5.58
}

# Load contacts and the upper VDD bus.
foreach x {-32 -16 16 32} {
    foreach y {16.25 23.75} { stack_to $x $y 3 }
    paint_rect metal3 [expr {$x-0.45}] 23.75 [expr {$x+0.45}] 25.3
    # Rise from the already-connected M3 trunk.  Starting this stack at M1
    # would overlap the resistor guard metal at this longer load geometry.
    stack_from3_to $x 24.8 5
}
paint_rect metal5 -44 24.4 44 25.3
make_port VDD 5 metal5 -1 24.4 1 25.3

# Differential divider outputs leave adjacent to the slave loads.
foreach {name number x} [list DIV_P 7 16 DIV_N 8 32] {
    make_port $name $number metal3 [expr {$x-0.45}] 13.5 [expr {$x+0.45}] 15.5
}

# Four feedback nets occupy two upper metals at ordered heights.  A lower
# route's endpoint vertical stops before the next route crosses it.
foreach {gate lane output layer highest y} [list \
        -12  -8  32 metal4 4 8 \
         12   8 -16 metal5 5 10 \
        -36 -40  16 metal5 5 12 \
         36  40 -32 metal4 4 14] {
    if {$lane == $gate} {
        stack_to $gate 0.25 $highest
    } else {
        # M5 track-source rails occupy the device row.  Leave the gate on M3,
        # move into an open channel, and only then rise to the route metal.
        stack_to $gate 0.25 3
        paint_rect metal3 [expr {min($gate,$lane)-0.38}] -0.13 \
            [expr {max($gate,$lane)+0.38}] 0.63
        stack_from3_to $lane 0.25 $highest
    }
    stack_from3_to $output 6.0 $highest
    paint_rect $layer [expr {$lane-0.38}] 0.25 [expr {$lane+0.38}] [expr {$y+0.38}]
    paint_rect $layer [expr {$output-0.38}] 6.0 [expr {$output+0.38}] [expr {$y+0.38}]
    paint_rect $layer [expr {min($lane,$output)-0.38}] [expr {$y-0.38}] \
        [expr {max($lane,$output)+0.38}] [expr {$y+0.38}]
}

# Clock gates: even uses P/N and odd swaps N/P.
foreach x {-30 30} {
    stack_to $x -12.70 5
    paint_rect metal5 [expr {$x-0.38}] -15.38 [expr {$x+0.38}] -12.32
}
paint_rect metal5 -39.38 -15.38 30.38 -14.62
foreach x {-18 18} {
    stack_to $x -12.70 4
    paint_rect metal4 [expr {$x-0.38}] -16.38 [expr {$x+0.38}] -12.32
}
paint_rect metal4 -37.38 -16.38 18.38 -15.62
paint_rect metal5 -39.38 -25.0 -38.62 -14.62
paint_rect metal4 -37.38 -25.0 -36.62 -15.62
make_port CLK_P 1 metal5 -39.38 -25.0 -38.62 -23.5
make_port CLK_N 2 metal4 -37.38 -25.0 -36.62 -23.5

# Shared programmable tail bias.
foreach x {-24 24} {
    stack_to $x -23.70 4
    paint_rect metal4 -35.38 -24.08 [expr {$x+0.38}] -23.32
}
paint_rect metal4 -35.38 -25.0 -34.62 -23.32
make_port VBIAS 4 metal4 -35.38 -25.0 -34.62 -23.5

# Matched reset pulldowns establish complementary master/slave state.
foreach x {-8 8} {
    # Two fingers provide a center diffusion and a pair of outer diffusions,
    # so drain and source can be contacted without landing on the gate.
    mos_terminal_strap $x -18 0.75 {-0.8 0.8} 3
    mos_terminal_strap $x -18 -0.75 {0.0} 3
    manual_gate_bottom $x -19.35 0.55 {-0.4 0.4}
    set gate_stack_x [expr {$x < 0 ? $x-2.0 : $x+2.0}]
    paint_rect metal1 [expr {min($x,$gate_stack_x)-0.38}] -20.0 \
        [expr {max($x,$gate_stack_x)+0.38}] -19.4
    stack_to $gate_stack_x -19.70 5
    paint_rect metal3 [expr {$x-0.38}] -22.0 [expr {$x+0.38}] -18.75
}
paint_rect metal5 -10.38 -20.08 10.38 -19.32
paint_rect metal5 -0.38 -25.0 0.38 -19.47
make_port RESET 3 metal5 -0.38 -25.0 0.38 -23.5

# Reset drains reach MASTER_N and DIV_P on the open inner sides.
paint_rect metal3 -16.38 -17.25 -7.62 -16.49
paint_rect metal3 -16.38 -17.25 -15.62 5.75
paint_rect metal3 7.62 -17.25 16.38 -16.49
paint_rect metal3 15.62 -17.25 16.38 5.75

# Contacted substrate guard and local tail-source returns.
paint_rect psubdiff -48 -27 -47.2 28
paint_rect psubdiff 47.2 -27 48 28
paint_rect psubdiff -48 -27 48 -26.2
paint_rect psubdiff -48 27.2 48 28
paint_rect metal1 -48 -27 -47.2 28
paint_rect metal1 47.2 -27 48 28
paint_rect metal1 -48 -27 48 -26.2
paint_rect metal1 -48 27.2 48 28
foreach x {-45 -39 -33 -27 -21 -15 -9 -3 3 9 15 21 27 33 39 45} {
    substrate_contact $x -26.6
    substrate_contact $x 27.6
}
foreach y {-23 -17 -11 -5 1 7 13 19 25} {
    substrate_contact -47.6 $y
    substrate_contact 47.6 $y
}
paint_rect metal3 -47.6 -22.45 47.6 -21.55
stack_to -47.5 -22.0 3
stack_to 47.5 -22.0 3
stack_to -47.5 -25.5 5
paint_rect metal5 -47.95 -25.5 -47.05 2.0
make_port VSS 6 metal5 -47.95 -2.0 -47.05 0.0

save /work/cml_divider_by_2
gds write /work/cml_divider_by_2.gds
quit -noprompt
