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
load cdr_sampler_hier

set signal_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 6 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set clock_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 8 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set tail_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 10 l 0.28 nf 4 guard 0 topc 0 botc 0 full_metal 0]
set load_cell [magic::gencell_makecell gf180mcu::ppolyf_u \
    w 2 l 5.00 guard 1 full_metal 1]

units microns
foreach {cell instance x y} [list \
        $signal_cell XEVEN_XDN -36 4 $signal_cell XEVEN_XLP -28 4 \
        $signal_cell XEVEN_XLN -20 4 $signal_cell XEVEN_XDP -12 4 \
        $clock_cell XEVEN_XCT -30 -8 $clock_cell XEVEN_XCH -18 -8 \
        $tail_cell XEVEN_XTAIL -24 -18 \
        $load_cell XEVEN_XRP -32 20 $load_cell XEVEN_XRN -16 20 \
        $signal_cell XODD_XDN 12 4 $signal_cell XODD_XLP 20 4 \
        $signal_cell XODD_XLN 28 4 $signal_cell XODD_XDP 36 4 \
        $clock_cell XODD_XCT 18 -8 $clock_cell XODD_XCH 30 -8 \
        $tail_cell XODD_XTAIL 24 -18 \
        $load_cell XODD_XRP 16 20 $load_cell XODD_XRN 32 20] {
    getcell $cell child 0 0 parent $x $y
    identify $instance
}

select top cell
flatten cdr_sampler
load cdr_sampler
units microns
paint_rect pwell -48 -27 48 28

# Signal quartets use track/hold/hold/track ordering with equal centroids.
foreach x {-36 -28 -20 -12 12 20 28 36} {
    mos_terminal_strap $x 4 1.75 {-0.8 0.8} 3
    mos_terminal_strap $x 4 -1.75 {0.0} 3
}
foreach x {-36 -12 12 36} { manual_gate_bottom $x 0.65 0.55 {-0.4 0.4} }
foreach x {-28 -20 20 28} { manual_gate_top $x 7.10 0.55 {-0.4 0.4} }

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

    paint_rect metal4 [expr {$hold_l-0.45}] 1.80 [expr {$hold_r+0.45}] 2.70
    stack_to $hold_l 2.25 4
    stack_to $hold_r 2.25 4
    paint_rect metal4 [expr {$hold_clk-0.45}] -5.75 [expr {$hold_clk+0.45}] 2.70
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

# Cross-coupled latch gates: Q_N drives XLP on M4, Q_P drives XLN on M5.
foreach {qp qn xlp xln} [list -32 -16 -28 -20 16 32 20 28] {
    stack_to $qn 11.0 4
    paint_rect metal4 [expr {$xlp-0.38}] 7.48 [expr {$qn+0.38}] 11.38
    stack_to $xlp 7.50 4
    stack_to $qp 13.0 5
    paint_rect metal5 [expr {$qp-0.38}] 12.62 [expr {$xln+0.38}] 13.38
    paint_rect metal5 [expr {$xln-0.38}] 7.48 [expr {$xln+0.38}] 13.38
    stack_to $xln 7.50 5
}

# Load contacts and the upper VDD bus.
foreach x {-32 -16 16 32} {
    foreach y {17.5 22.5} { stack_to $x $y 3 }
    paint_rect metal3 [expr {$x-0.45}] 22.5 [expr {$x+0.45}] 25.3
    stack_to $x 24.8 5
}
paint_rect metal5 -44 24.4 44 25.3
make_port VDD 6 metal5 -1 24.4 1 25.3

# Differential outputs leave on short M3 trunks adjacent to their loads.
foreach {name number x} [list EVEN_P 8 -32 EVEN_N 9 -16 ODD_P 10 16 ODD_N 11 32] {
    make_port $name $number metal3 [expr {$x-0.45}] 14.0 [expr {$x+0.45}] 16.0
}

# Matched data inputs drive the outer quartet devices on M5.
foreach {x name number rail_x} [list -36 DATA_N 2 -43 -12 DATA_P 1 -41 \
                                       12 DATA_N 2 -43 36 DATA_P 1 -41] {
    stack_to $x 0.25 5
    paint_rect metal5 [expr {$x-0.38}] -1.5 [expr {$x+0.38}] 0.63
    paint_rect metal5 $rail_x -1.88 [expr {$x+0.38}] -1.12
}
paint_rect metal5 -43.38 -25.0 -42.62 -1.12
paint_rect metal5 -41.38 -25.0 -40.62 -1.12
make_port DATA_N 2 metal5 -43.38 -25.0 -42.62 -23.5
make_port DATA_P 1 metal5 -41.38 -25.0 -40.62 -23.5

# Clock gates: even uses P/N and odd swaps N/P.
foreach {x layer rail_x} [list -30 metal5 -39 -18 metal4 -37 18 metal4 -37 30 metal5 -39] {
    stack_to $x -12.70 [expr {$layer eq "metal5" ? 5 : 4}]
    paint_rect $layer $rail_x -13.08 [expr {$x+0.38}] -12.32
}
paint_rect metal5 -39.38 -25.0 -38.62 -12.32
paint_rect metal4 -37.38 -25.0 -36.62 -12.32
make_port CLK_P 3 metal5 -39.38 -25.0 -38.62 -23.5
make_port CLK_N 4 metal4 -37.38 -25.0 -36.62 -23.5

# Shared programmable tail bias.
foreach x {-24 24} {
    stack_to $x -23.70 4
    paint_rect metal4 -35.38 -24.08 [expr {$x+0.38}] -23.32
}
paint_rect metal4 -35.38 -25.0 -34.62 -23.32
make_port VBIAS 5 metal4 -35.38 -25.0 -34.62 -23.5

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
paint_rect metal3 -47.6 -22.45 -21.6 -21.55
paint_rect metal3 21.6 -22.45 47.6 -21.55
stack_to -47.5 -22.0 3
stack_to 47.5 -22.0 3
stack_to -47.5 -25.5 5
paint_rect metal5 -47.95 -25.5 -47.05 2.0
make_port VSS 7 metal5 -47.95 -2.0 -47.05 0.0

save /work/cdr_sampler
gds write /work/cdr_sampler.gds
quit -noprompt
