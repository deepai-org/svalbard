# SPDX-License-Identifier: Apache-2.0
# Compact matched layout for one half-rate Alexander CML boundary.

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
load cml_alexander_boundary_hier

set switch_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 10 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set tail_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 15 l 0.28 nf 4 guard 0 topc 0 botc 0 full_metal 0]
set load_cell [magic::gencell_makecell gf180mcu::ppolyf_u \
    w 2 l 9.00 guard 1 full_metal 1]

units microns
foreach {cell instance x y} [list \
        $switch_cell XE_XNX_BP -33 15 $switch_cell XE_XNX_BN -27 15 \
        $switch_cell XE_XNY_BN -21 15 $switch_cell XE_XNY_BP -15 15 \
        $switch_cell XE_XAP -29 4 $switch_cell XE_XAN -19 4 \
        $tail_cell XE_XTAIL -24 -12 \
        $load_cell XE_XRP -33 31 $load_cell XE_XRN -15 31 \
        $switch_cell XL_XNX_BP 15 15 $switch_cell XL_XNX_BN 21 15 \
        $switch_cell XL_XNY_BN 27 15 $switch_cell XL_XNY_BP 33 15 \
        $switch_cell XL_XAP 19 4 $switch_cell XL_XAN 29 4 \
        $tail_cell XL_XTAIL 24 -12 \
        $load_cell XL_XRP 15 31 $load_cell XL_XRN 33 31] {
    getcell $cell child 0 0 parent $x $y
    identify $instance
}

select top cell
flatten cml_alexander_boundary
load cml_alexander_boundary
units microns
paint_rect pwell -46 -25 46 40

# Contact every switching-device terminal and gate before routing.
foreach x {-33 -27 -21 -15 -29 -19 15 21 27 33 19 29} {
    mos_terminal_strap $x [expr {$x == -29 || $x == -19 || $x == 19 || $x == 29 ? 4 : 15}] 2.75 {-0.8 0.8} 3
    mos_terminal_strap $x [expr {$x == -29 || $x == -19 || $x == 19 || $x == 29 ? 4 : 15}] -2.75 {0.0} 3
    set cy [expr {$x == -29 || $x == -19 || $x == 19 || $x == 29 ? 4 : 15}]
    manual_gate_bottom $x [expr {$cy-5.35}] 0.55 {-0.4 0.4}
}

# Within each XOR, the upper sources form two adjacent selector branches.
foreach cx {-24 24} {
    foreach {left right lower} [list [expr {$cx-9}] [expr {$cx-3}] [expr {$cx-5}] \
                                      [expr {$cx+3}] [expr {$cx+9}] [expr {$cx+5}]] {
        paint_rect metal3 [expr {$left-0.38}] 11.87 [expr {$right+0.38}] 12.63
        paint_rect metal3 [expr {($left+$right)/2.0-0.38}] 6.75 \
            [expr {($left+$right)/2.0+0.38}] 12.63
        paint_rect metal3 [expr {min(($left+$right)/2.0,$lower)-0.38}] 6.37 \
            [expr {max(($left+$right)/2.0,$lower)+0.38}] 7.13
    }
}

# P and N drain pairs use equal-length staggered M4 buses.  Their outer M3
# risers continue directly to the local loads, avoiding output-node crossings.
foreach cx {-24 24} {
    set pleft [expr {$cx-9}]
    set pright [expr {$cx+3}]
    set nleft [expr {$cx-3}]
    set nright [expr {$cx+9}]
    foreach x [list $pleft $pright] {
        paint_rect metal3 [expr {$x-0.38}] 17.75 [expr {$x+0.38}] 19.0
        stack_from3_to $x 19.0 4
    }
    paint_rect metal4 [expr {$pleft-0.38}] 18.62 [expr {$pright+0.38}] 19.38
    foreach x [list $nleft $nright] {
        paint_rect metal3 [expr {$x-0.38}] 17.75 [expr {$x+0.38}] 21.0
        stack_from3_to $x 21.0 4
    }
    paint_rect metal4 [expr {$nleft-0.38}] 20.62 [expr {$nright+0.38}] 21.38
    paint_rect metal3 [expr {$pleft-0.38}] 19.0 [expr {$pleft+0.38}] 26.5
    paint_rect metal3 [expr {$nright-0.38}] 21.0 [expr {$nright+0.38}] 26.5
    foreach x [list $pleft $nright] { stack_to $x 26.5 3 }
}

# Lower-pair common sources meet the local tail drain on M4.
foreach cx {-24 24} {
    foreach x [list [expr {$cx-5}] [expr {$cx+5}]] { stack_from3_to $x 1.25 4 }
    paint_rect metal4 [expr {$cx-5.38}] 0.87 [expr {$cx+5.38}] 1.63
    paint_rect metal4 [expr {$cx-0.38}] -5.5 [expr {$cx+0.38}] 1.63
    mos_terminal_strap $cx -12 6.5 {-1.6 0.0 1.6} 3
    mos_terminal_strap $cx -12 -6.5 {-0.8 0.8} 3
    stack_from3_to $cx -5.5 4
    manual_gate_bottom $cx -19.85 1.35 {-1.2 -0.4 0.4 1.2}
}

# Upper B gates: outer devices are BP on M5; inner devices are BN on M4.
foreach cx {-24 24} {
    foreach x [list [expr {$cx-9}] [expr {$cx+9}]] { stack_to $x 9.25 5 }
    paint_rect metal5 [expr {$cx-9.38}] 8.87 [expr {$cx+9.38}] 9.63
    foreach x [list [expr {$cx-3}] [expr {$cx+3}]] {
        stack_to $x 9.25 4
        paint_rect metal4 [expr {$x-0.38}] 9.25 [expr {$x+0.38}] 10.75
    }
    paint_rect metal4 [expr {$cx-3.38}] 10.37 [expr {$cx+3.38}] 11.13
}

# PREV drives the lower selector of the EARLY XOR.
stack_to -29 -1.75 5
paint_rect metal5 -44 -2.13 -28.62 -1.37
make_port PREV_P 1 metal5 -44 -2.13 -42.5 -1.37
stack_to -19 -1.75 5
paint_rect metal5 -19.38 -1.75 -18.62 -0.25
paint_rect metal5 -42 -0.63 -19.0 0.13
make_port PREV_N 2 metal5 -42 -0.63 -40.5 0.13

# EDGE drives the EARLY B pair and the LATE lower selector on matched high metal.
paint_rect metal5 -33.38 7.12 19.38 7.88
paint_rect metal5 -33.38 7.5 -32.62 9.25
paint_rect metal5 18.62 -1.75 19.38 7.88
stack_to 19 -1.75 5
make_port EDGE_P 3 metal5 -44 7.12 -42.5 7.88
paint_rect metal5 -44 7.12 -33.0 7.88
paint_rect metal4 -42 10.37 -21.0 11.13
paint_rect metal4 -40.38 -4.0 -39.62 10.75
paint_rect metal4 -40.38 -4.38 -39.62 -3.62
paint_rect metal5 -40.38 -4.38 -39.62 -3.62
via_at via4 -40 -4.0
paint_rect metal5 -40.0 -4.38 29.38 -3.62
paint_rect metal5 28.62 -4.0 29.38 -1.75
stack_to 29 -1.75 5
make_port EDGE_N 4 metal4 -42 10.37 -40.5 11.13

# CUR drives only the upper B pair of the LATE XOR.
paint_rect metal5 15.0 8.87 44 9.63
make_port CUR_P 5 metal5 42.5 8.87 44 9.63
paint_rect metal4 26.62 8.87 27.38 11.38
paint_rect metal4 27.0 10.62 44 11.38
make_port CUR_N 6 metal4 42.5 10.62 44 11.38

# Shared programmable tail bias below both cells.
foreach x {-24 24} { stack_to $x -20.25 4 }
paint_rect metal4 -24.38 -20.63 24.38 -19.87
paint_rect metal4 -0.38 -23.0 0.38 -19.87
make_port VBIAS 7 metal4 -0.38 -23.0 0.38 -21.5

# Load tops meet a wide M5 VDD rail through local via stacks.
foreach x {-33 -15 15 33} {
    stack_to $x 35.5 5
    paint_rect metal5 [expr {$x-0.45}] 35.5 [expr {$x+0.45}] 38.0
}
paint_rect metal5 -42 37.55 42 38.45
make_port VDD 8 metal5 -1 37.55 1 38.45

# Contacted substrate guard ring and local tail-source returns.
paint_rect psubdiff -46 -25 -45.2 40
paint_rect psubdiff 45.2 -25 46 40
paint_rect psubdiff -46 -25 46 -24.2
paint_rect psubdiff -46 39.2 46 40
paint_rect metal1 -46 -25 -45.2 40
paint_rect metal1 45.2 -25 46 40
paint_rect metal1 -46 -25 46 -24.2
paint_rect metal1 -46 39.2 46 40
foreach x {-43 -37 -31 -25 -19 -13 -7 -1 5 11 17 23 29 35 41} {
    substrate_contact $x -24.6
    substrate_contact $x 39.6
}
foreach y {-22 -16 -10 -4 2 8 14 20 26 32 38} {
    substrate_contact -45.6 $y
    substrate_contact 45.6 $y
}
foreach {cx edge} {-24 -45.6 24 45.6} {
    paint_rect metal3 [expr {min($cx,$edge)-0.38}] -18.88 \
        [expr {max($cx,$edge)+0.38}] -18.12
    stack_to $edge -18.5 3
}
stack_to -45.6 -23.0 5
paint_rect metal5 -45.98 -23.0 -45.22 -18.5
make_port VSS 9 metal5 -45.98 -23.0 -45.22 -21.5

# Differential outputs are short M5-accessible pins beside their load risers.
foreach {name number x} [list EARLY_P 10 -33 EARLY_N 11 -15 \
                               LATE_P 12 15 LATE_N 13 33] {
    stack_from3_to $x 23.0 5
    make_port $name $number metal5 [expr {$x-0.45}] 22.5 \
        [expr {$x+0.45}] 24.0
}

save /work/cml_alexander_boundary
gds write /work/cml_alexander_boundary.gds
quit -noprompt
