# SPDX-License-Identifier: Apache-2.0
# Compact symmetric GF180 layout for one regenerative CML VCO delay tile.

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

proc make_port {name number layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    label $name FreeSans 0.5 0 0 0 c $layer
    port make $number
}

proc substrate_contact {x y} {
    paint_rect psubdiffcont [expr {$x-0.25}] [expr {$y-0.30}] \
        [expr {$x+0.25}] [expr {$y+0.30}]
}

proc terminal_strap {cx cy yoff xs highest} {
    set y [expr {$cy+$yoff}]
    foreach xoff $xs {
        set x [expr {$cx+$xoff}]
        paint_rect metal1 [expr {$x-0.28}] [expr {min($cy,$y)-0.28}] \
            [expr {$x+0.28}] [expr {max($cy,$y)+0.28}]
        via_at via1 $x $y
        if {$highest >= 3} { via_at via2 $x $y }
        if {$highest >= 4} { via_at via3 $x $y }
        if {$highest >= 5} { via_at via4 $x $y }
    }
    paint_rect metal2 [expr {$cx+[lindex $xs 0]-0.38}] [expr {$y-0.38}] \
        [expr {$cx+[lindex $xs end]+0.38}] [expr {$y+0.38}]
    if {$highest >= 3} {
        paint_rect metal3 [expr {$cx+[lindex $xs 0]-0.38}] [expr {$y-0.38}] \
            [expr {$cx+[lindex $xs end]+0.38}] [expr {$y+0.38}]
    }
    if {$highest >= 4} {
        paint_rect metal4 [expr {$cx+[lindex $xs 0]-0.38}] [expr {$y-0.38}] \
            [expr {$cx+[lindex $xs end]+0.38}] [expr {$y+0.38}]
    }
    if {$highest >= 5} {
        paint_rect metal5 [expr {$cx+[lindex $xs 0]-0.38}] [expr {$y-0.38}] \
            [expr {$cx+[lindex $xs end]+0.38}] [expr {$y+0.38}]
    }
}

proc manual_gate_bottom {cx y half_width xs highest} {
    paint_rect polysilicon [expr {$cx-$half_width}] $y \
        [expr {$cx+$half_width}] [expr {$y+0.25}]
    foreach xoff $xs {
        set x [expr {$cx+$xoff}]
        paint_rect polysilicon [expr {$x-0.20}] [expr {$y-0.65}] \
            [expr {$x+0.20}] [expr {$y+0.25}]
        paint_rect polycontact [expr {$x-0.115}] [expr {$y-0.565}] \
            [expr {$x+0.115}] [expr {$y-0.335}]
        paint_rect metal1 [expr {$x-0.30}] [expr {$y-0.65}] \
            [expr {$x+0.30}] [expr {$y-0.05}]
    }
    paint_rect metal1 [expr {$cx+[lindex $xs 0]-0.35}] [expr {$y-0.65}] \
        [expr {$cx+[lindex $xs end]+0.35}] [expr {$y-0.05}]
    paint_rect metal2 [expr {$cx+[lindex $xs 0]-0.35}] [expr {$y-0.65}] \
        [expr {$cx+[lindex $xs end]+0.35}] [expr {$y-0.05}]
    if {$highest >= 3} {
        paint_rect metal3 [expr {$cx+[lindex $xs 0]-0.35}] [expr {$y-0.65}] \
            [expr {$cx+[lindex $xs end]+0.35}] [expr {$y-0.05}]
    }
    via_at via1 $cx [expr {$y-0.35}]
    if {$highest >= 3} { via_at via2 $cx [expr {$y-0.35}] }
    return [expr {$y-0.35}]
}

proc manual_gate_top_single {cx cy width highest} {
    set contact_y [expr {$cy+$width/2.0+0.80}]
    set route_y [expr {$cy+$width/2.0+0.70}]
    paint_rect polysilicon [expr {$cx-0.20}] [expr {$cy+$width/2.0+0.10}] \
        [expr {$cx+0.20}] [expr {$contact_y+0.18}]
    paint_rect polycontact [expr {$cx-0.115}] [expr {$contact_y-0.115}] \
        [expr {$cx+0.115}] [expr {$contact_y+0.115}]
    foreach layer {metal1 metal2} {
        paint_rect $layer [expr {$cx-0.30}] [expr {$route_y-0.30}] \
            [expr {$cx+0.30}] [expr {$route_y+0.30}]
    }
    via_at via1 $cx $route_y
    if {$highest >= 3} {
        paint_rect metal3 [expr {$cx-0.30}] [expr {$route_y-0.30}] \
            [expr {$cx+0.30}] [expr {$route_y+0.30}]
        via_at via2 $cx $route_y
    }
    if {$highest >= 4} {
        paint_rect metal4 [expr {$cx-0.30}] [expr {$route_y-0.30}] \
            [expr {$cx+0.30}] [expr {$route_y+0.30}]
        via_at via3 $cx $route_y
    }
    if {$highest >= 5} {
        paint_rect metal5 [expr {$cx-0.30}] [expr {$route_y-0.30}] \
            [expr {$cx+0.30}] [expr {$route_y+0.30}]
        via_at via4 $cx $route_y
    }
    return $route_y
}

crashbackups stop
set cell_name cml_vco_delay
set cap_l 0.8
set cap_w 4.0
set load_l 5.25
set main_tail_w 10.0
set latch_tail_w 4.0
set split_control 0
if {[info exists ::env(VCO_CELL_NAME)]} { set cell_name $::env(VCO_CELL_NAME) }
if {[info exists ::env(VCO_CAP_L)]} { set cap_l $::env(VCO_CAP_L) }
if {[info exists ::env(VCO_CAP_W)]} { set cap_w $::env(VCO_CAP_W) }
if {[info exists ::env(VCO_LOAD_L)]} { set load_l $::env(VCO_LOAD_L) }
if {[info exists ::env(VCO_MAIN_TAIL_W)]} { set main_tail_w $::env(VCO_MAIN_TAIL_W) }
if {[info exists ::env(VCO_LATCH_TAIL_W)]} { set latch_tail_w $::env(VCO_LATCH_TAIL_W) }
if {[info exists ::env(VCO_SPLIT_CONTROL)]} { set split_control $::env(VCO_SPLIT_CONTROL) }
set cap_left_xoff [expr {-$cap_l/2.0-0.44}]
set cap_right_xoff [expr {$cap_l/2.0+0.44}]
# The cap diffusion contact moves with channel length.  Keep it out of the
# fixed x=+/-11 regenerative-output trunks: medium-long members move inward;
# shorter and very-long members are already clear on opposite sides.
set cap_center 15.0
if {$cap_l > 5.8 && $cap_l < 8.5} { set cap_center 14.0 }
set cap_left_center [expr {-$cap_center}]
set cap_right_center $cap_center
set cap_left_vss_end [expr {$cap_left_center+$cap_right_xoff+0.38}]
set cap_right_vss_start [expr {$cap_right_center+$cap_left_xoff-0.38}]
set cap_terminal_off [expr {$cap_w/2.0-1.0}]
set cap_bottom_y [expr {11.0-$cap_terminal_off}]
set cap_top_y [expr {11.0+$cap_terminal_off}]
set cap_gate_y [expr {11.0-$cap_w/2.0-0.35}]
set load_off [expr {$load_l/2.0-0.010}]
set load_bottom_y [expr {23.0-$load_off}]
set load_top_y [expr {23.0+$load_off}]
set main_tail_off [expr {$main_tail_w/2.0-1.0}]
set main_tail_top_y [expr {-13.0+$main_tail_off}]
set main_tail_bottom_y [expr {-13.0-$main_tail_off}]
set main_tail_gate_y [expr {-13.0-$main_tail_w/2.0-0.35}]
set main_tail_gate_stack_y [expr {$main_tail_gate_y-0.35}]
set latch_tail_off [expr {$latch_tail_w/2.0-1.0}]
set latch_tail_top_y [expr {-13.0+$latch_tail_off}]
set latch_tail_bottom_y [expr {-13.0-$latch_tail_off}]
set latch_tail_gate_y [expr {-13.0-$latch_tail_w/2.0-0.35}]
set latch_tail_gate_stack_y [expr {$latch_tail_gate_y-0.35}]
set vctrl_y $main_tail_gate_stack_y

load ${cell_name}_hier

set input_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 5 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set latch_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 4 l 0.28 nf 1 guard 0 topc 0 botc 0 full_metal 0]
set input_tail [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w $main_tail_w l 0.28 nf 4 guard 0 topc 0 botc 0 full_metal 0]
set latch_tail [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w $latch_tail_w l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set mos_cap [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w $cap_w l $cap_l nf 1 guard 0 topc 0 botc 0 full_metal 0]
set load_cell [magic::gencell_makecell gf180mcu::ppolyf_u \
    w 2 l $load_l guard 1 full_metal 1]

units microns
# The four switching devices are one mirror-symmetric row.  The driven pair
# occupies the outer positions and the weaker regenerative pair the inner.
foreach {cell instance x y} [list \
        $input_cell XMP -15 0 $latch_cell XLP -5 0 \
        $latch_cell XLN 5 0 $input_cell XMN 15 0 \
        $input_tail XMT -8 -13 $latch_tail XMLT 8 -13 \
        $mos_cap XCP $cap_left_center 11 $mos_cap XCN $cap_right_center 11 \
        $load_cell XRP -15 23 $load_cell XRN 15 23] {
    getcell $cell child 0 0 parent $x $y
    identify $instance
}

select top cell
flatten $cell_name
load $cell_name
units microns
paint_rect pwell -27 -24 27 32

# Switching drains form short, matched M3 output trunks to local loads/caps.
foreach x {-15 15} {
    terminal_strap $x 0 1.5 {-0.8 0.8} 3
    terminal_strap $x 0 -1.5 {0.0} 5
    manual_gate_bottom $x -2.85 0.55 {-0.4 0.4} 3
}
foreach x {-5 5} {
    terminal_strap $x 0 1.0 {-0.4} 3
    terminal_strap $x 0 -1.0 {0.4} 4
}
manual_gate_top_single -5 0 4 4
manual_gate_top_single 5 0 4 5
paint_rect metal3 -16.2 1.05 -3.8 1.95
paint_rect metal3 3.8 1.05 16.2 1.95

# Driven-pair sources share one nested M5 rail; regenerative sources share M4.
paint_rect metal5 -16.2 -1.95 16.2 -1.05
paint_rect metal4 -5.38 -1.38 8.38 -0.62

# Tail devices sit directly below the switching row with independent drains.
terminal_strap -8 -13 $main_tail_off {-1.6 0.0 1.6} 5
terminal_strap -8 -13 [expr {-$main_tail_off}] {-0.8 0.8} 3
manual_gate_bottom -8 $main_tail_gate_y 1.35 {-1.2 -0.4 0.4 1.2} 4
paint_rect metal5 -8.38 [expr {$main_tail_top_y-0.38}] -7.62 -1.05

terminal_strap 8 -13 $latch_tail_off {-0.8 0.8} 4
terminal_strap 8 -13 [expr {-$latch_tail_off}] {0.0} 3
manual_gate_bottom 8 $latch_tail_gate_y 0.55 {-0.4 0.4} 4
paint_rect metal4 7.62 [expr {$latch_tail_top_y-0.38}] 8.38 -0.62

# The normal cell shares one tail control.  The margin-study cell exposes the
# driven-pair and regenerative tails independently so frequency can be tuned
# without surrendering loop gain at slow/hot corners.
stack_to -8 $main_tail_gate_stack_y 4
stack_to 8 $latch_tail_gate_stack_y 4
if {$split_control} {
    paint_rect metal4 -24 [expr {$vctrl_y-0.38}] -7.62 \
        [expr {$vctrl_y+0.38}]
    make_port VCTRL_MAIN 5 metal4 -24 [expr {$vctrl_y-0.38}] \
        -22.5 [expr {$vctrl_y+0.38}]
    paint_rect metal4 7.62 [expr {$latch_tail_gate_stack_y-0.38}] 12.5 \
        [expr {$latch_tail_gate_stack_y+0.38}]
    make_port VCTRL_REGEN 8 metal4 11.0 \
        [expr {$latch_tail_gate_stack_y-0.38}] 12.5 \
        [expr {$latch_tail_gate_stack_y+0.38}]
} else {
    paint_rect metal4 -24 [expr {$vctrl_y-0.38}] -7.62 \
        [expr {$vctrl_y+0.38}]
    paint_rect metal4 7.62 [expr {$vctrl_y-0.38}] 8.38 \
        [expr {$latch_tail_gate_stack_y+0.38}]
    paint_rect metal4 -8.38 [expr {$vctrl_y-0.38}] 8.38 \
        [expr {$vctrl_y+0.38}]
    make_port VCTRL 5 metal4 -24 [expr {$vctrl_y-0.38}] \
        -22.5 [expr {$vctrl_y+0.38}]
}

# Differential inputs enter on matched M5 drops at the outer device gates.
foreach {x name number} [list -15 INP 1 15 INN 2] {
    stack_to $x -3.20 5
    paint_rect metal5 [expr {$x-0.38}] -22.0 [expr {$x+0.38}] -2.82
    make_port $name $number metal5 [expr {$x-0.45}] -22.0 \
        [expr {$x+0.45}] -20.8
}

# Cross-coupled latch gates use different upper metals so the two feedback
# paths cross geometrically without becoming one net.
stack_to -5 2.70 4
stack_to 5 2.70 5
stack_to -11 7.0 4
stack_to 11 7.0 4
stack_to -11 9.0 5
paint_rect metal3 -11.38 1.05 -10.62 9.38
paint_rect metal3 10.62 1.05 11.38 7.38
paint_rect metal4 -5.38 2.32 -4.62 7.38
paint_rect metal4 -5.38 6.62 11.38 7.38
paint_rect metal5 4.62 2.32 5.38 9.38
paint_rect metal5 -11.38 8.62 5.38 9.38

# MOS-cap gates attach to outputs; both diffusion terminals return to VSS.
foreach x [list $cap_left_center $cap_right_center] {
    terminal_strap $x 11 $cap_terminal_off [list $cap_left_xoff] 3
    terminal_strap $x 11 [expr {-$cap_terminal_off}] [list $cap_right_xoff] 3
    set gate_y [manual_gate_bottom $x $cap_gate_y 1.60 {0.0} 3]
    paint_rect metal3 [expr {$x-0.38}] 1.05 [expr {$x+0.38}] [expr {$gate_y+0.38}]
}

# Loads are directly above their output devices and join a wide M5 VDD rail.
foreach x {-15 15} {
    stack_to $x $load_bottom_y 5
    stack_to $x $load_top_y 5
}
stack_to -11 1.50 5
stack_to 11 1.50 5
paint_rect metal5 -15.38 [expr {$load_bottom_y-0.38}] -10.62 [expr {$load_bottom_y+0.38}]
paint_rect metal5 10.62 [expr {$load_bottom_y-0.38}] 15.38 [expr {$load_bottom_y+0.38}]
paint_rect metal5 -11.38 1.12 -10.62 [expr {$load_bottom_y+0.38}]
paint_rect metal5 10.62 1.12 11.38 [expr {$load_bottom_y+0.38}]
paint_rect metal5 -23 24.70 23 27.00
make_port VDD 6 metal5 -1 24.70 1 27.00

# Output ports sit on the short drain trunks, before any upper-metal escape.
make_port OUTP 3 metal3 -16.2 1.05 -12.5 1.95
make_port OUTN 4 metal3 12.5 1.05 16.2 1.95

# Contacted substrate guard is also the low-inductance VSS return.  Tail
# sources and both terminals of each MOS cap meet it symmetrically on M3.
paint_rect psubdiff -27 -24 -26.2 32
paint_rect psubdiff 26.2 -24 27 32
paint_rect psubdiff -27 -24 27 -23.2
paint_rect psubdiff -27 31.2 27 32
paint_rect metal1 -27 -24 -26.2 32
paint_rect metal1 26.2 -24 27 32
paint_rect metal1 -27 -24 27 -23.2
paint_rect metal1 -27 31.2 27 32
foreach x {-24 -18 -12 -6 0 6 12 18 24} {
    substrate_contact $x -23.6
    substrate_contact $x 31.6
}
foreach y {-21 -15 -9 -3 3 9 15 21 27} {
    substrate_contact -26.6 $y
    substrate_contact 26.6 $y
}
stack_to -26.5 -22.5 5
make_port VSS 7 metal5 -26.95 -22.5 -26.05 -20.5

# Tail sources return horizontally on M3.
paint_rect metal3 -26.6 [expr {$main_tail_bottom_y-0.45}] -5.6 [expr {$main_tail_bottom_y+0.45}]
paint_rect metal3 7.6 [expr {$latch_tail_bottom_y-0.45}] 26.6 [expr {$latch_tail_bottom_y+0.45}]
foreach {x y} [list -26.6 $main_tail_bottom_y 26.6 $latch_tail_bottom_y] { stack_to $x $y 3 }

# Each MOS-cap diffusion pair returns on its nearest guard side.
paint_rect metal3 -26.6 [expr {$cap_bottom_y-0.45}] $cap_left_vss_end \
    [expr {$cap_bottom_y+0.45}]
paint_rect metal3 -26.6 [expr {$cap_top_y-0.45}] $cap_left_vss_end \
    [expr {$cap_top_y+0.45}]
paint_rect metal3 $cap_right_vss_start [expr {$cap_bottom_y-0.45}] 26.6 \
    [expr {$cap_bottom_y+0.45}]
paint_rect metal3 $cap_right_vss_start [expr {$cap_top_y-0.45}] 26.6 \
    [expr {$cap_top_y+0.45}]
foreach {x y} [list -26.6 $cap_bottom_y -26.6 $cap_top_y \
        26.6 $cap_bottom_y 26.6 $cap_top_y] {
    stack_to $x $y 3
}

save $cell_name
gds write /work/${cell_name}.gds
quit -noprompt
