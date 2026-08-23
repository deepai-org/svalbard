# SPDX-License-Identifier: Apache-2.0
# Compact matched wideband CML data-restoration stage.

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
load cml_data_restorer_stage_hier
set pair_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 10 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set tail_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 12 l 0.28 nf 4 guard 0 topc 0 botc 0 full_metal 0]
set load_cell [magic::gencell_makecell gf180mcu::ppolyf_u \
    w 2 l 4.50 guard 1 full_metal 1]
units microns
foreach {cell instance x y} [list \
        $pair_cell XIP -4 2 $pair_cell XIN 4 2 \
        $tail_cell XTAIL 0 -11 \
        $load_cell XRP -4 16 $load_cell XRN 4 16] {
    getcell $cell child 0 0 parent $x $y
    identify $instance
}
select top cell
flatten cml_data_restorer_stage
load cml_data_restorer_stage
units microns
paint_rect pwell -14 -22 14 24

# Matched two-finger input pair, short common source, and local four-finger tail.
foreach x {-4 4} {
    mos_terminal_strap $x 2 2.75 {-0.8 0.8} 3
    mos_terminal_strap $x 2 -2.75 {0.0} 3
    manual_gate_bottom $x -3.35 0.55 {-0.4 0.4}
}
paint_rect metal3 -4.45 -1.20 4.45 -0.30
paint_rect metal3 -0.45 -6.25 0.45 -0.30
mos_terminal_strap 0 -11 4.75 {-1.6 0.0 1.6} 3
mos_terminal_strap 0 -11 -4.75 {-0.8 0.8} 3
manual_gate_bottom 0 -17.35 1.35 {-1.2 -0.4 0.4 1.2}
paint_rect metal3 -2.4 -16.20 2.4 -15.30

# Adjacent 4.5 um loads balance slow-corner gain and arbitrary-data settling.
foreach x {-4 4} {
    foreach y {13.75 18.25} { stack_to $x $y 3 }
    paint_rect metal3 [expr {$x-0.45}] 4.30 [expr {$x+0.45}] 13.75
    paint_rect metal3 [expr {$x-0.45}] 18.25 [expr {$x+0.45}] 22.0
    stack_from3_to $x 21.5 5
}
paint_rect metal5 -10 21.1 10 22.0
make_port VDD 4 metal5 -1 21.1 1 22.0
make_port OUT_P 6 metal3 -4.45 9.5 -3.55 11.0
make_port OUT_N 7 metal3 3.55 9.5 4.45 11.0

# Differential gates escape downward on matched M5 tracks.
foreach {x name number} [list -4 IN_P 1 4 IN_N 2] {
    stack_to $x -3.70 5
    paint_rect metal5 [expr {$x-0.38}] -20.0 [expr {$x+0.38}] -3.32
    make_port $name $number metal5 [expr {$x-0.45}] -20.0 \
        [expr {$x+0.45}] -18.8
}
stack_to 0 -17.70 4
paint_rect metal4 -0.38 -20.0 0.38 -17.32
make_port VBIAS 3 metal4 -0.45 -20.0 0.45 -18.8

# Contacted guard and wide local VSS return.
paint_rect psubdiff -14 -22 -13.2 24
paint_rect psubdiff 13.2 -22 14 24
paint_rect psubdiff -14 -22 14 -21.2
paint_rect psubdiff -14 23.2 14 24
paint_rect metal1 -14 -22 -13.2 24
paint_rect metal1 13.2 -22 14 24
paint_rect metal1 -14 -22 14 -21.2
paint_rect metal1 -14 23.2 14 24
foreach x {-11 -7 -3 1 5 9} {
    substrate_contact $x -21.6
    substrate_contact $x 23.6
}
foreach y {-19 -13 -7 -1 5 11 17 23} {
    substrate_contact -13.6 $y
    substrate_contact 13.6 $y
}
paint_rect metal3 -13.6 -16.20 13.6 -15.30
stack_to -13.5 -15.75 3
stack_to 13.5 -15.75 3
stack_to -13.5 -20.5 5
paint_rect metal5 -13.95 -20.5 -13.05 2.0
make_port VSS 5 metal5 -13.95 -2.0 -13.05 0.0

save /work/cml_data_restorer_stage
gds write /work/cml_data_restorer_stage.gds
quit -noprompt
