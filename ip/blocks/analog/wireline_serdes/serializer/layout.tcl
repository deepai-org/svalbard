# SPDX-License-Identifier: Apache-2.0
# Compact common-centroid half-rate CML serializer for GF180MCU.

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

crashbackups stop
load cml_serializer_2to1_hier

set data_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 6 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set select_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 8 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set tail_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 10 l 0.28 nf 4 guard 0 topc 0 botc 0 full_metal 0]
set load_cell [magic::gencell_makecell gf180mcu::ppolyf_u \
    w 2 l 7.50 guard 1 full_metal 1]

units microns
# E_P/O_P/O_N/E_N is a mirror-symmetric common-centroid data array.
foreach {cell instance x y} [list \
        $data_cell XEVEN_P -12 4 $data_cell XODD_P -4 4 \
        $data_cell XODD_N 4 4 $data_cell XEVEN_N 12 4 \
        $select_cell XSELECT_E -8 -8 $select_cell XSELECT_O 8 -8 \
        $tail_cell XTAIL 0 -18 \
        $load_cell XRN -8 20 $load_cell XRP 8 20] {
    getcell $cell child 0 0 parent $x $y
    identify $instance
}

select top cell
flatten cml_serializer_2to1
load cml_serializer_2to1
units microns
paint_rect pwell -24 -27 24 28

# Data-pair terminals and distributed two-finger gate contacts.
foreach x {-12 -4 4 12} {
    mos_terminal_strap $x 4 1.75 {-0.8 0.8} 3
    mos_terminal_strap $x 4 -1.75 {0.0} 3
    manual_gate_bottom $x 0.65 0.55 {-0.4 0.4}
}
foreach {name number x} [list EVEN_P 1 -12 ODD_P 3 -4 ODD_N 4 4 EVEN_N 2 12] {
    make_port $name $number metal1 [expr {$x-0.72}] -0.02 \
        [expr {$x+0.72}] 0.60
}

# Same-polarity drains share compact output buses beneath local loads.
paint_rect metal3 -13.2 5.30 -2.8 6.20
paint_rect metal3 2.8 5.30 13.2 6.20
foreach x {-8 8} {
    paint_rect metal3 [expr {$x-0.45}] 5.30 [expr {$x+0.45}] 16.25
}
make_port SER_N 11 metal3 -8.45 12.0 -7.55 14.0
make_port SER_P 10 metal3 7.55 12.0 8.45 14.0

# The outer EVEN sources use M5; the inner ODD sources use M4.  Both nets
# remain mirror-balanced despite crossing the center of the data array.
foreach x {-12 12} { stack_to $x 2.25 5 }
paint_rect metal5 -12.38 1.87 12.38 2.63
paint_rect metal5 -8.38 -5.75 -7.62 2.63
stack_from3_to -8 -5.75 5
foreach x {-4 4} { stack_to $x 2.25 4 }
paint_rect metal4 -4.38 1.87 4.38 2.63
paint_rect metal4 7.62 -5.75 8.38 2.63
paint_rect metal4 3.62 1.87 8.38 2.63
stack_from3_to 8 -5.75 4

# Complementary clock selectors and the directly adjacent shared tail.
foreach x {-8 8} {
    mos_terminal_strap $x -8 2.25 {-0.8 0.8} 3
    mos_terminal_strap $x -8 -2.25 {0.0} 3
    manual_gate_bottom $x -12.35 0.55 {-0.4 0.4}
}
make_port CLK_P 5 metal1 -8.60 -12.92 -7.40 -12.48
make_port CLK_N 6 metal1 7.40 -12.92 8.60 -12.48
paint_rect metal3 -8.38 -10.63 8.38 -9.87
paint_rect metal3 -0.45 -14.0 0.45 -9.87

mos_terminal_strap 0 -18 4.0 {-1.6 0.0 1.6} 3
mos_terminal_strap 0 -18 -4.0 {-0.8 0.8} 3
manual_gate_bottom 0 -23.35 1.35 {-1.2 -0.4 0.4 1.2}
make_port VBIAS 7 metal1 -1.55 -24.02 1.55 -23.40

# Resistor contacts, local output landings, and a low-impedance VDD strap.
foreach x {-8 8} {
    foreach y {16.25 23.75} { stack_to $x $y 3 }
    stack_from3_to $x 24.8 5
    paint_rect metal3 [expr {$x-0.45}] 23.75 [expr {$x+0.45}] 25.3
}
paint_rect metal5 -18 24.4 18 25.3
make_port VDD 8 metal5 -1 24.4 1 25.3

# Contacted substrate guard ring and short, wide local tail return.
paint_rect psubdiff -24 -27 -23.2 28
paint_rect psubdiff 23.2 -27 24 28
paint_rect psubdiff -24 -27 24 -26.2
paint_rect psubdiff -24 27.2 24 28
paint_rect metal1 -24 -27 -23.2 28
paint_rect metal1 23.2 -27 24 28
paint_rect metal1 -24 -27 24 -26.2
paint_rect metal1 -24 27.2 24 28
foreach x {-21 -15 -9 -3 3 9 15 21} {
    substrate_contact $x -26.6
    substrate_contact $x 27.6
}
foreach y {-23 -17 -11 -5 1 7 13 19 25} {
    substrate_contact -23.6 $y
    substrate_contact 23.6 $y
}
paint_rect metal3 -23.6 -22.38 23.6 -21.62
stack_to -23.5 -22.0 3
stack_to 23.5 -22.0 3
stack_to -23.5 -25.5 5
paint_rect metal5 -23.95 -25.5 -23.05 2.0
make_port VSS 9 metal5 -23.95 -2.0 -23.05 0.0

save /work/cml_serializer_2to1
gds write /work/cml_serializer_2to1.gds
quit -noprompt
