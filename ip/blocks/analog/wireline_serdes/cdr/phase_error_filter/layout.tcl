# SPDX-License-Identifier: Apache-2.0
# Symmetric GF180 layout for the dual-interleave CML phase-error combiner.

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
load cml_phase_error_filter_hier

set switch_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 8 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set tail_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 8 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set load_cell [magic::gencell_makecell gf180mcu::ppolyf_u \
    w 2 l 4.00 guard 1 full_metal 1]

units microns
foreach {cell instance x y} [list \
        $switch_cell XE0P -24.5 5 $switch_cell XE0N -17.5 5 \
        $switch_cell XL0P -10.5 5 $switch_cell XL0N -3.5 5 \
        $switch_cell XL1P 3.5 5 $switch_cell XL1N 10.5 5 \
        $switch_cell XE1P 17.5 5 $switch_cell XE1N 24.5 5 \
        $tail_cell XTE0 -21 -12 $tail_cell XTL0 -7 -12 \
        $tail_cell XTL1 7 -12 $tail_cell XTE1 21 -12 \
        $load_cell XRP -7 21 $load_cell XRN 7 21] {
    getcell $cell child 0 0 parent $x $y
    identify $instance
}

select top cell
flatten cml_phase_error_filter
load cml_phase_error_filter
units microns
paint_rect pwell -31 -28 31 30

# Eight equal input devices form a mirrored E0/L0/L1/E1 row.  Each pair has
# its own tail immediately below it, keeping the four dynamic source nodes local.
foreach x {-24.5 -17.5 -10.5 -3.5 3.5 10.5 17.5 24.5} {
    mos_terminal_strap $x 5 2.25 {-0.8 0.8} 3
    mos_terminal_strap $x 5 -2.25 {0.0} 3
    manual_gate_bottom $x 0.65 0.55 {-0.4 0.4}
}
foreach x {-21 -7 7 21} {
    mos_terminal_strap $x -12 2.25 {-0.8 0.8} 3
    mos_terminal_strap $x -12 -2.25 {0.0} 3
    manual_gate_bottom $x -16.35 0.55 {-0.4 0.4}
}

# Local pair-source buses drop directly into their local tail drain on M4.
foreach cx {-21 -7 7 21} {
    set left [expr {$cx-3.5}]
    set right [expr {$cx+3.5}]
    foreach x [list $left $right] { stack_from3_to $x 2.75 4 }
    paint_rect metal4 [expr {$left-0.38}] 2.37 [expr {$right+0.38}] 3.13
    paint_rect metal4 [expr {$cx-0.38}] -9.75 [expr {$cx+0.38}] 3.13
    stack_from3_to $cx -9.75 4
}

# ERRP and ERRN use separate symmetric M4/M5 summing rails.  Each device has
# only a short vertical branch; the two output/load risers are centered.
foreach x {-17.5 -10.5 3.5 24.5} {
    stack_from3_to $x 7.25 4
    paint_rect metal4 [expr {$x-0.38}] 7.25 [expr {$x+0.38}] 10.5
}
paint_rect metal4 -25.0 10.12 25.0 10.88
foreach x {-24.5 -3.5 10.5 17.5} {
    stack_from3_to $x 7.25 5
    paint_rect metal5 [expr {$x-0.38}] 7.25 [expr {$x+0.38}] 12.5
}
paint_rect metal5 -25.0 12.12 25.0 12.88

# Load bottoms and compact output pins sit on the two centered summing nodes.
paint_rect metal4 -7.38 10.5 -6.62 18.67
stack_to -7 18.67 4
paint_rect metal5 6.62 12.5 7.38 18.67
stack_to 7 18.67 5
make_port ERRP 12 metal4 -7.45 14.0 -6.55 15.5
make_port ERRN 13 metal5 6.55 14.0 7.45 15.5

# Resistor tops rise into a wide M5 VDD rail.
foreach x {-7 7} {
    stack_to $x 23.33 5
    paint_rect metal5 [expr {$x-0.45}] 23.33 [expr {$x+0.45}] 27.0
}
paint_rect metal5 -28 26.55 28 27.45
make_port VDD 10 metal5 -1 26.55 1 27.45

# All input gates are individually accessible on vertical M5 tracks.
foreach {x name number} [list -24.5 E0P 1 -17.5 E0N 2 -10.5 L0P 3 -3.5 L0N 4 \
                               3.5 L1P 7 10.5 L1N 8 17.5 E1P 5 24.5 E1N 6] {
    stack_to $x 0.30 5
    paint_rect metal5 [expr {$x-0.38}] -25.8 [expr {$x+0.38}] 0.68
    make_port $name $number metal5 [expr {$x-0.45}] -25.8 \
        [expr {$x+0.45}] -24.6
}

# One matched bias rail contacts all four tail gates.
foreach x {-21 -7 7 21} { stack_to $x -16.70 4 }
paint_rect metal4 -27 -17.08 27 -16.32
make_port VBIAS 9 metal4 -27 -17.08 -25.5 -16.32

# Contacted substrate guard ring and short tail-source returns.
paint_rect psubdiff -31 -28 -30.2 30
paint_rect psubdiff 30.2 -28 31 30
paint_rect psubdiff -31 -28 31 -27.2
paint_rect psubdiff -31 29.2 31 30
paint_rect metal1 -31 -28 -30.2 30
paint_rect metal1 30.2 -28 31 30
paint_rect metal1 -31 -28 31 -27.2
paint_rect metal1 -31 29.2 31 30
foreach x {-28 -22 -16 -10 -4 2 8 14 20 26} {
    substrate_contact $x -27.6
    substrate_contact $x 29.6
}
foreach y {-25 -19 -13 -7 -1 5 11 17 23 29} {
    substrate_contact -30.6 $y
    substrate_contact 30.6 $y
}
foreach {x edge} {-21 -30.6 -7 -30.6 7 30.6 21 30.6} {
    paint_rect metal3 [expr {min($x,$edge)-0.38}] -14.63 \
        [expr {max($x,$edge)+0.38}] -13.87
    stack_to $edge -14.25 3
}
stack_to -30.6 -26.0 5
paint_rect metal5 -30.98 -26.0 -30.22 -14.25
make_port VSS 11 metal5 -30.98 -26.0 -30.22 -24.5

save /work/cml_phase_error_filter
gds write /work/cml_phase_error_filter.gds
quit -noprompt
