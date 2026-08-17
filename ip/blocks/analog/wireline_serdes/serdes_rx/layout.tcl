# SPDX-License-Identifier: Apache-2.0
# Matched GF180 layout for the two-stage static CML receiver.

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
    via_at via1 $x $y
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

proc mos_terminal_strap {cx cy yoff xs} {
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
load serdes_rx_hier

set main_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 10 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set buffer_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 5 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set threshold_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 2 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set tail_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 10 l 0.28 nf 5 guard 0 topc 0 botc 0 full_metal 0]
set threshold_tail_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 2 l 0.28 nf 4 guard 0 topc 0 botc 0 full_metal 0]
set switch_cell [magic::gencell_makecell gf180mcu::pfet_03v3 \
    w 5 l 0.28 nf 1 guard 0 topc 0 botc 0 full_metal 0]
set stage1_load [magic::gencell_makecell gf180mcu::ppolyf_u \
    w 2 l 4.57 guard 1 full_metal 1]
set stage2_load [magic::gencell_makecell gf180mcu::ppolyf_u \
    w 2 l 3.43 guard 1 full_metal 1]
set bandwidth_load [magic::gencell_makecell gf180mcu::ppolyf_u \
    w 1 l 1.40 guard 1 full_metal 1]

units microns
foreach {cell instance x y} [list \
        $main_cell XINP -25 0 $main_cell XINN -17 0 \
        $threshold_cell XTHP -25 14 $threshold_cell XTHN -17 14 \
        $tail_cell XTAIL1 -21 -14 $threshold_tail_cell XTAILTH -21 8 \
        $buffer_cell XBUF2P 11 0 $buffer_cell XBUF2N 19 0 \
        $tail_cell XTAIL2 15 -14 \
        $stage1_load XRL1P -25 31 $stage1_load XRL1N -17 31 \
        $stage2_load XRL2P 11 31 $stage2_load XRL2N 19 31 \
        $bandwidth_load XRBWP -33 31 $bandwidth_load XRBWN -9 31 \
        $bandwidth_load XRBW2P 3 31 $bandwidth_load XRBW2N 27 31 \
        $switch_cell XSWP -33 20 $switch_cell XSWN -9 20 \
        $switch_cell XSW2P 3 20 $switch_cell XSW2N 27 20] {
    getcell $cell child 0 0 parent $x $y
    identify $instance
}

select top cell
flatten serdes_rx
load serdes_rx
units microns

paint_rect pwell -38 -24 32 39
paint_rect nwell -36 16.5 30.8 25.0

# Main and buffer pairs use identical two-finger terminal and gate access.
foreach x {-25 -17} {
    mos_terminal_strap $x 0 4.0 {-0.8 0.8}
    mos_terminal_strap $x 0 -4.0 {0.0}
}
manual_gate_bottom -25 -5.35 0.55 {-0.4 0.4}
manual_gate_bottom -17 -5.35 0.55 {-0.4 0.4}
foreach x {11 19} {
    mos_terminal_strap $x 0 1.5 {-0.8 0.8}
    mos_terminal_strap $x 0 -1.5 {0.0}
    manual_gate_top $x 2.60 0.55 {-0.4 0.4}
}

# The smaller threshold pair is centered directly above the first stage.
foreach x {-25 -17} {
    mos_terminal_strap $x 14 0.8 {-0.8 0.8}
    mos_terminal_strap $x 14 -0.8 {0.0}
    manual_gate_top $x 15.10 0.55 {-0.4 0.4}
}

# Tail devices are directly below their source rails.
set tail_gate_offsets {-1.6 -0.8 0.0 0.8 1.6}
set tail_even {-2.0 -0.4 1.2}
set tail_odd {-1.2 0.4 2.0}
foreach x {-21 15} {
    mos_terminal_strap $x -14 4.0 $tail_even
    mos_terminal_strap $x -14 -4.0 $tail_odd
    manual_gate_bottom $x -19.35 1.75 $tail_gate_offsets
    paint_rect metal3 [expr {$x-2.38}] -10.38 [expr {$x+1.58}] -9.62
}
set small_tail_gates {-1.2 -0.4 0.4 1.2}
mos_terminal_strap -21 8 0.8 {-1.6 0.0 1.6}
mos_terminal_strap -21 8 -0.8 {-0.8 0.8}
manual_gate_bottom -21 6.65 1.35 $small_tail_gates

# Collect the three matched source/tail nodes with short metal3 straps.
foreach {x1 x2 center source_y drain_y} [list -25 -17 -21 -4 -10 11 19 15 -1.5 -10] {
    paint_rect metal3 [expr {$x1-1.2}] [expr {$source_y-0.45}] \
        [expr {$x2+1.2}] [expr {$source_y+0.45}]
    foreach x [list $x1 $x2] {
        via_at via2 $x $source_y
    }
    foreach xoff {-2.0 -0.4 1.2} { via_at via2 [expr {$center+$xoff}] $drain_y }
    paint_rect metal3 [expr {$center-0.45}] $drain_y \
        [expr {$center+0.45}] [expr {$source_y+0.45}]
}
paint_rect metal2 -26.2 12.75 -15.8 13.65
paint_rect metal2 -21.45 8.8 -20.55 13.65

# High-speed trunks are offset outward from the gate-contact centerlines, then
# mirrored about each stage.  This avoids drain-to-gate shorts without putting
# either polarity on a longer local route.
foreach {device_x node_x drain_y} [list -25 -26.6 4.0 -17 -15.4 4.0 11 9.4 1.5 19 20.6 1.5] {
    paint_rect metal3 [expr {$node_x-0.55}] [expr {$drain_y-0.45}] \
        [expr {$node_x+0.55}] 29.4
    foreach xoff {-0.8 0.8} { via_at via2 [expr {$device_x+$xoff}] $drain_y }
    paint_rect metal3 [expr {min($node_x,$device_x-1.2)}] [expr {$drain_y-0.45}] \
        [expr {max($node_x,$device_x+1.2)}] [expr {$drain_y+0.45}]
}
foreach {device_x node_x} [list -25 -26.6 -17 -15.4] {
    foreach xoff {-0.8 0.8} { via_at via2 [expr {$device_x+$xoff}] 14.8 }
    paint_rect metal3 [expr {min($node_x,$device_x-1.2)}] 14.35 \
        [expr {max($node_x,$device_x+1.2)}] 15.25
}

# Load resistor contacts.  Every top terminal rises to the common VDD bus;
# base-load bottoms land directly on their corresponding signal trunk.
foreach {x roff} [list -25 2.615 -17 2.615 11 2.045 19 2.045 \
                         -33 1.030 -9 1.030 3 1.030 27 1.030] {
    foreach y [list [expr {31-$roff}] [expr {31+$roff}]] {
        paint_rect metal1 [expr {$x-0.30}] [expr {$y-0.30}] \
            [expr {$x+0.30}] [expr {$y+0.30}]
        via_at via1 $x $y
        via_at via2 $x $y
        paint_rect metal2 [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
        paint_rect metal3 [expr {$x-0.45}] [expr {$y-0.38}] \
            [expr {$x+0.45}] [expr {$y+0.38}]
    }
    set top_y [expr {31+$roff}]
    paint_rect metal3 [expr {$x-0.45}] $top_y [expr {$x+0.45}] 35.8
    foreach layer {metal3 metal4 metal5} {
        paint_rect $layer [expr {$x-0.38}] 35.12 [expr {$x+0.38}] 35.88
    }
    via_at via3 $x 35.5
    via_at via4 $x 35.5
}
foreach {load_x node_x bottom_y} [list -25 -26.6 28.385 -17 -15.4 28.385 \
                                        11 9.4 28.955 19 20.6 28.955] {
    paint_rect metal3 [expr {min($load_x,$node_x)-0.45}] [expr {$bottom_y-0.38}] \
        [expr {max($load_x,$node_x)+0.45}] [expr {$bottom_y+0.38}]
}

# Single-finger PMOS bandwidth switches are mirrored about each differential
# stage.  Resistor-side and signal-side terminal routing is geometrically equal.
foreach {x node_x mirror} [list -33 -26.6 0 -9 -15.4 1 3 9.4 0 27 20.6 1] {
    manual_gate_top $x 22.60 0.22 {0.0}
    if {$mirror == 0} {
        set resistor_terminal [expr {$x-0.4}]
        set node_terminal [expr {$x+0.4}]
    } else {
        set resistor_terminal [expr {$x+0.4}]
        set node_terminal [expr {$x-0.4}]
    }
    foreach terminal [list $resistor_terminal $node_terminal] {
        paint_rect metal1 [expr {$terminal-0.28}] 19.72 [expr {$terminal+0.28}] 20.28
        via_at via1 $terminal 20
        paint_rect metal2 [expr {$terminal-0.24}] 19.76 [expr {$terminal+0.24}] 20.24
    }
    set resistor_riser [expr {$mirror == 0 ? $x-2.0 : $x+2.0}]
    set node_riser [expr {$mirror == 0 ? $x+2.0 : $x-2.0}]
    paint_rect metal2 [expr {min($resistor_terminal,$resistor_riser)-0.24}] 19.76 \
        [expr {max($resistor_terminal,$resistor_riser)+0.24}] 20.24
    paint_rect metal2 [expr {min($node_terminal,$node_riser)-0.24}] 19.76 \
        [expr {max($node_terminal,$node_riser)+0.24}] 20.24
    foreach riser [list $resistor_riser $node_riser] {
        via_at via2 $riser 20
        paint_rect metal2 [expr {$riser-0.38}] 19.62 [expr {$riser+0.38}] 20.38
        paint_rect metal3 [expr {$riser-0.38}] 19.62 [expr {$riser+0.38}] 20.38
    }
    paint_rect metal3 [expr {$resistor_riser-0.45}] 19.62 \
        [expr {$resistor_riser+0.45}] 30.35
    paint_rect metal3 [expr {min($x,$resistor_riser)-0.45}] 29.59 \
        [expr {max($x,$resistor_riser)+0.45}] 30.35
    paint_rect metal3 [expr {min($node_riser,$node_x)-0.38}] 19.62 \
        [expr {max($node_riser,$node_x)+0.38}] 20.38
    set gate_stack [expr {$mirror == 0 ? $x+2.0 : $x-2.0}]
    paint_rect metal1 [expr {min($x,$gate_stack)-0.35}] 23.00 \
        [expr {max($x,$gate_stack)+0.35}] 23.60
    stack_to $gate_stack 23.30 4
}

# Active-low bandwidth control stays on metal4, away from every signal trunk.
paint_rect metal4 -35.38 22.92 29.38 23.68
make_port BW_EN_N 6 metal4 -4 22.92 -2 23.68

# Matched input and threshold controls use separate upper-metal corridors.
foreach {x name number} [list -25 RXP 1 -17 RXN 2] {
    stack_to $x -5.70 4
    paint_rect metal4 [expr {$x-0.38}] -22.0 [expr {$x+0.38}] -5.32
    make_port $name $number metal4 [expr {$x-0.50}] -22.0 [expr {$x+0.50}] -20.8
}
foreach {device_x gate_x name number} [list -25 -23 VTHP 3 -17 -19 VTHN 4] {
    paint_rect metal1 [expr {min($device_x,$gate_x)-0.35}] 15.50 \
        [expr {max($device_x,$gate_x)+0.35}] 16.10
    stack_to $gate_x 15.70 5
    paint_rect metal5 [expr {$gate_x-0.38}] 15.32 [expr {$gate_x+0.38}] 34.0
    make_port $name $number metal5 [expr {$gate_x-0.50}] 33.0 [expr {$gate_x+0.50}] 34.0
}

# Equal-length, layer-swapped routes connect stage one to stage two.  Each path
# uses two M4/M5 transitions, balancing series resistance and via capacitance.
foreach layer {metal3 metal4} { paint_rect $layer -26.98 7.62 -26.22 8.38 }
via_at via3 -26.6 8.0
paint_rect metal4 -26.98 7.62 -6.62 8.38
paint_rect metal4 -7.38 7.62 -6.62 8.38
paint_rect metal5 -7.38 7.62 11.38 8.38
via_at via4 -7 8
stack_to 11 3.20 5
paint_rect metal5 10.62 2.82 11.38 8.38

foreach layer {metal3 metal4 metal5} { paint_rect $layer -15.78 9.62 -15.02 10.38 }
via_at via3 -15.4 10.0
via_at via4 -15.4 10.0
paint_rect metal5 -15.78 9.62 1.38 10.38
paint_rect metal4 0.62 9.62 19.38 10.38
via_at via4 1 10
stack_to 19 3.20 4
paint_rect metal4 18.62 2.82 19.38 10.38

# Tail bias uses metal5 so it can cross both input and internal-signal routes.
foreach x {-21 15} { stack_to $x -19.70 5 }
stack_to -21 6.10 4
paint_rect metal5 -23.88 -20.08 15.38 -19.32
paint_rect metal4 -23.88 -20.08 -23.12 6.48
paint_rect metal4 -23.88 5.72 -20.62 6.48
paint_rect metal4 -23.88 -20.08 -23.12 -19.32
paint_rect metal5 -23.88 -20.08 -23.12 -19.32
via_at via4 -23.5 -19.70
make_port VBIAS 5 metal5 -4 -20.08 -2 -19.32

make_port OUTP 9 metal3 8.85 25.0 9.95 27.0
make_port OUTN 10 metal3 20.05 25.0 21.15 27.0

# VDD rail and a contacted PMOS well tap.
paint_rect metal5 -35.5 35.1 30 36.0
paint_rect nsubdiff 29.85 22.62 30.55 23.38
nwell_contact 30.2 23.0
paint_rect metal1 29.82 22.62 30.58 23.38
stack_to 30.2 23.0 5
paint_rect metal5 29.82 22.62 30.58 36.0
make_port VDD 7 metal5 -1 35.1 1 36.0

# Tail sources return locally on metal2, following the proven transmitter
# pattern and staying below the upper-metal bias/control crossings.
foreach xoff {-1.2 0.4 2.0} {
    via_at via2 [expr {-21+$xoff}] -18
    via_at via2 [expr {15+$xoff}] -18
}
paint_rect metal2 -37.98 -18.6 -18.6 -17.4
paint_rect metal3 -37.98 -18.6 -18.6 -17.4
paint_rect metal2 12.4 -18.6 31.98 -17.4
paint_rect metal3 12.4 -18.6 31.98 -17.4
paint_rect metal2 -37.98 6.8 -18.6 7.6
via_at via1 -37.6 -18
via_at via1 31.6 -18
via_at via1 -37.6 7.2
paint_rect metal5 -37.0 -23.0 31.0 -22.1

paint_rect psubdiff -38 -24 -37.2 39
paint_rect psubdiff 31.2 -24 32 39
paint_rect psubdiff -38 -24 32 -23.2
paint_rect psubdiff -38 38.2 32 39
paint_rect metal1 -38 -24 -37.2 39
paint_rect metal1 31.2 -24 32 39
paint_rect metal1 -38 -24 32 -23.2
paint_rect metal1 -38 38.2 32 39
foreach x {-35 -29 -23 -17 -11 -5 1 7 13 19 25 29} {
    substrate_contact $x -23.6
    substrate_contact $x 38.6
}
foreach y {-20 -14 -8 -2 4 10 16 22 28 34} {
    substrate_contact -37.6 $y
    substrate_contact 31.6 $y
}
stack_to -37 -22.5 5
paint_rect metal5 -37.45 -22.5 -36.55 7.58
make_port VSS 8 metal5 -37.45 -2 -36.55 0

save /work/serdes_rx
gds write /work/serdes_rx.gds
quit -noprompt
