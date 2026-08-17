# SPDX-License-Identifier: Apache-2.0
# GF180 layout for the experimental 3.3 V CML transmitter output cell.

proc paint_rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}

proc via_at {layer x y} {
    set half 0.18
    paint_rect $layer [expr {$x-$half}] [expr {$y-$half}] \
        [expr {$x+$half}] [expr {$y+$half}]
}

proc via_pair_x {layer x y} {
    foreach xoff {-0.32 0.32} {
        via_at $layer [expr {$x+$xoff}] $y
    }
}

proc substrate_contact {x y} {
    paint_rect psubdiffcont [expr {$x-0.25}] [expr {$y-0.30}] \
        [expr {$x+0.25}] [expr {$y+0.30}]
}

proc nwell_contact {x y} {
    paint_rect nsubdiffcont [expr {$x-0.25}] [expr {$y-0.30}] \
        [expr {$x+0.25}] [expr {$y+0.30}]
}

proc label_net {name layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    label $name FreeSans 0.5 0 0 0 c $layer
}

proc make_port {name number layer x1 y1 x2 y2} {
    label_net $name $layer $x1 $y1 $x2 $y2
    port make $number
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
load serdes_tx_hier

set diff_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 20 l 0.28 nf 10 guard 0 topc 0 botc 0 full_metal 0]
set tail_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 20 l 0.5 nf 10 guard 0 topc 0 botc 0 full_metal 0]
set base_load_cell [magic::gencell_makecell gf180mcu::ppolyf_u \
    w 1 l 0.8 guard 1 full_metal 1]
set trim_load_cell [magic::gencell_makecell gf180mcu::ppolyf_u \
    w 1 l 0.8 guard 1 full_metal 1]
set load_switch_cell [magic::gencell_makecell gf180mcu::pfet_03v3 \
    w 20 l 0.28 nf 5 guard 0 topc 0 botc 0 full_metal 0]

units microns
foreach {cell instance x y} [list \
        $diff_cell MDIFF_P -5 0 \
        $diff_cell MDIFF_N 5 0 \
        $tail_cell MTAIL 0 -24 \
        $base_load_cell RBASE_P -34.4 15.73 \
        $base_load_cell RBASE_N 34.4 15.73 \
        $trim_load_cell RTRIM_P0 -8.8 15.73 \
        $trim_load_cell RTRIM_P1 -15.2 15.73 \
        $trim_load_cell RTRIM_P2 -21.6 15.73 \
        $trim_load_cell RTRIM_P3 -28.0 15.73 \
        $trim_load_cell RTRIM_N0 8.8 15.73 \
        $trim_load_cell RTRIM_N1 15.2 15.73 \
        $trim_load_cell RTRIM_N2 21.6 15.73 \
        $trim_load_cell RTRIM_N3 28.0 15.73 \
        $load_switch_cell MSW_P0 -8.8 42 \
        $load_switch_cell MSW_P1 -15.2 42 \
        $load_switch_cell MSW_P2 -21.6 42 \
        $load_switch_cell MSW_P3 -28.0 42 \
        $load_switch_cell MSW_N0 8.8 42 \
        $load_switch_cell MSW_N1 15.2 42 \
        $load_switch_cell MSW_N2 21.6 42 \
        $load_switch_cell MSW_N3 28.0 42] {
    getcell $cell child 0 0 parent $x $y
    identify $instance
}

# Materialize the generated device geometry before adding top-level routes.
select top cell
flatten serdes_tx
load serdes_tx
units microns

if {[info exists ::env(SERDES_TX_DEVICES_ONLY)]} {
    save /work/serdes_tx_devices
    quit -noprompt
}

# One continuous p-well encloses the switching core, resistor shields, and its
# grounded guard ring.  Two explicit n-wells enclose the PMOS trim switches.
paint_rect pwell -38.0 -38.0 38.0 30.5
paint_rect nwell -32.0 31.0 -4.4 54.5
paint_rect nwell 4.4 31.0 32.0 54.5

# Poly straps join the fingers and every finger receives a distributed gate contact.
set diff_gates {-3.6 -2.8 -2.0 -1.2 -0.4 0.4 1.2 2.0 2.8 3.6}
set tail_gates {-4.59 -3.57 -2.55 -1.53 -0.51 0.51 1.53 2.55 3.57 4.59}
manual_gate -5 10.10 3.75 $diff_gates
manual_gate 5 10.10 3.75 $diff_gates
manual_gate_bottom -5 -10.35 3.75 $diff_gates
manual_gate_bottom 5 -10.35 3.75 $diff_gates
manual_gate 0 -13.90 4.82 $tail_gates
make_port VBIAS 5 metal1 -0.30 -13.45 0.30 -12.95

# Every PMOS switch finger is contacted at the quiet VDD-facing end.  The
# four static thermometer controls use separate upper metals, leaving the
# output buses on metal3 unobstructed.
set switch_gates {-1.6 -0.8 0.0 0.8 1.6}
set switch_even {-2.0 -0.4 1.2}
set switch_odd {-1.2 0.4 2.0}
foreach x {-28.0 -21.6 -15.2 -8.8 8.8 15.2 21.6 28.0} {
    manual_gate $x 52.10 1.75 $switch_gates
    mos_terminal_strap $x 42 -8.0 $switch_even
    mos_terminal_strap $x 42 8.0 $switch_odd
}

# Double-ended gate contacts are joined on metal4, crossing the drain/source
# buses without adding output-to-input shorts.  Both sides use identical stacks.
foreach x {-5 5} {
    foreach y {-10.70 10.70} {
        foreach layer {metal2 metal3 metal4} {
            paint_rect $layer [expr {$x-0.80}] [expr {$y-0.50}] \
                [expr {$x+0.80}] [expr {$y+0.50}]
        }
        via_pair_x via1 $x $y
        via_pair_x via2 $x $y
        via_pair_x via3 $x $y
    }
    paint_rect metal4 [expr {$x-0.60}] -11.20 \
        [expr {$x+0.60}] 11.20
}
make_port INP 1 metal4 -5.50 -1.0 -4.50 1.0
make_port INN 2 metal4 4.50 -1.0 5.50 1.0

# Alternate diffusion bars are collected on metal2 at opposite ends.
set even_diff {-4.0 -2.4 -0.8 0.8 2.4 4.0}
set odd_diff {-3.2 -1.6 0.0 1.6 3.2}
set even_tail {-5.1 -3.06 -1.02 1.02 3.06 5.1}
set odd_tail {-4.08 -2.04 0.0 2.04 4.08}
mos_terminal_strap -5 0 8.0 $even_diff
mos_terminal_strap -5 0 -8.0 $odd_diff
mos_terminal_strap 5 0 8.0 $even_diff
mos_terminal_strap 5 0 -8.0 $odd_diff
mos_terminal_strap 0 -24 8.0 $even_tail
mos_terminal_strap 0 -24 -8.0 $odd_tail

# The adjacent pair banks share a short, wide source rail.  The tail drain is
# directly beneath it, reducing this bandwidth-sensitive internal node from
# about 36 um to 8 um while retaining legal device-edge spacing.
paint_rect metal2 -9.4 -8.60 9.4 -7.40
paint_rect metal2 -0.70 -16.40 0.70 -7.60
paint_rect metal3 -9.4 -8.60 9.4 -7.40
paint_rect metal3 -0.70 -16.40 0.70 -7.60
paint_rect metal3 -5.5 -16.60 5.5 -15.40
foreach x {-8.2 -5.0 -1.8 1.8 5.0 8.2} {
    via_at via2 $x -8.0
}
foreach x {-3.06 0 3.06} {
    via_at via2 $x -16.0
}

# Resistor terminal landing pads and vias.  All load bottoms land on the
# outputs; trim tops connect only to their local PMOS drains.
foreach x {-34.4 -28.0 -21.6 -15.2 -8.8 8.8 15.2 21.6 28.0 34.4} {
    foreach y {15.0} {
        paint_rect metal1 [expr {$x-0.28}] [expr {$y-0.28}] \
            [expr {$x+0.28}] [expr {$y+0.28}]
        via_at via1 $x $y
        paint_rect metal2 [expr {$x-0.42}] [expr {$y-0.42}] \
            [expr {$x+0.42}] [expr {$y+0.42}]
    }
}
foreach x {-28.0 -21.6 -15.2 -8.8 8.8 15.2 21.6 28.0} {
    set y 16.46
    paint_rect metal1 [expr {$x-0.28}] [expr {$y-0.28}] \
        [expr {$x+0.28}] [expr {$y+0.28}]
    via_at via1 $x $y
    paint_rect metal2 [expr {$x-0.42}] [expr {$y-0.42}] \
        [expr {$x+0.42}] [expr {$y+0.42}]
    via_at via2 $x $y
    via_at via2 $x 34.0
    paint_rect metal3 [expr {$x-0.70}] 15.96 [expr {$x+0.70}] 34.50
}
foreach x {-34.4 34.4} {
    set y 16.46
    paint_rect metal1 [expr {$x-0.28}] [expr {$y-0.28}] \
        [expr {$x+0.28}] [expr {$y+0.28}]
    via_at via1 $x $y
    paint_rect metal2 [expr {$x-0.42}] [expr {$y-0.42}] \
        [expr {$x+0.42}] [expr {$y+0.42}]
    via_at via2 $x $y
    via_at via2 $x 50.0
    paint_rect metal3 [expr {$x-0.70}] 15.96 [expr {$x+0.70}] 50.50
}

# Matched outputs use identical metal3 buses and redundant transitions.  The
# long horizontal span is intentional: it is wide, symmetric, and stays below
# the resistor bank rather than passing across switch gates.
foreach x {-9 9} {
    if {$x < 0} {
        set device_x -5
    } else {
        set device_x 5
    }
    paint_rect metal2 [expr {$x-0.80}] 7.50 [expr {$x+0.80}] 8.50
    via_pair_x via2 $x 8.0
    if {$x < 0} {
        paint_rect metal3 -9.70 7.50 -0.60 8.50
    } else {
        paint_rect metal3 0.60 7.50 9.70 8.50
    }
    foreach xoff {-2.4 0 2.4} {
        via_at via2 [expr {$device_x+$xoff}] 8.0
    }
    paint_rect metal3 [expr {$x-0.70}] 7.50 [expr {$x+0.70}] 15.60
}
paint_rect metal3 -35.10 14.40 -8.30 15.60
paint_rect metal3 8.30 14.40 35.10 15.60
foreach x {-34.4 -28.0 -21.6 -15.2 -8.8 8.8 15.2 21.6 28.0 34.4} {
    via_at via2 $x 15.0
}

# A wide VDD rail joins the switch sources and always-on load tops.
paint_rect metal2 -35.2 49.40 35.2 50.60
paint_rect metal3 -35.2 49.40 35.2 50.60
foreach x {-28.0 -21.6 -15.2 -8.8 8.8 15.2 21.6 28.0} {
    via_pair_x via2 $x 50.0
}

# Contact both shared PMOS wells frequently and connect them to VDD.
foreach x {-31.4 -24.8 -18.4 -12.0 -5.2 5.2 12.0 18.4 24.8 31.4} {
    paint_rect nsubdiff [expr {$x-0.35}] 48.60 [expr {$x+0.35}] 49.40
    nwell_contact $x 49.0
    paint_rect metal1 [expr {$x-0.38}] 48.62 [expr {$x+0.38}] 49.38
    paint_rect metal2 [expr {$x-0.42}] 48.58 [expr {$x+0.42}] 49.50
    via_at via1 $x 49.0
}

# Thermometer controls.  Branch zero is innermost; branch three is outermost.
# Only static control nets climb through these compact, redundant via stacks.
foreach {idx layer xl xr} {0 metal2 -8.8 8.8 1 metal3 -15.2 15.2 2 metal4 -21.6 21.6 3 metal5 -28.0 28.0} {
    foreach x [list $xl $xr] {
        paint_rect metal1 [expr {$x-0.50}] 52.50 [expr {$x+0.50}] 53.10
        paint_rect metal2 [expr {$x-0.55}] 52.30 [expr {$x+0.55}] 53.10
        via_pair_x via1 $x 52.70
        if {$idx >= 1} {
            paint_rect metal3 [expr {$x-0.55}] 52.30 [expr {$x+0.55}] 53.10
            via_pair_x via2 $x 52.70
        }
        if {$idx >= 2} {
            paint_rect metal4 [expr {$x-0.55}] 52.30 [expr {$x+0.55}] 53.10
            via_pair_x via3 $x 52.70
        }
        if {$idx >= 3} {
            paint_rect metal5 [expr {$x-0.55}] 52.30 [expr {$x+0.55}] 53.10
            via_pair_x via4 $x 52.70
        }
    }
    paint_rect $layer [expr {$xl-0.50}] 52.35 [expr {$xr+0.50}] 53.05
    set label_x [lindex {0 -10 10 -22} $idx]
    make_port LOAD_EN${idx}_N [expr {6+$idx}] $layer \
        [expr {$label_x-0.45}] 52.35 [expr {$label_x+0.45}] 53.05
}

# The tail source is a wide local VSS rail.
paint_rect metal2 -6.0 -32.60 6.0 -31.40
paint_rect metal3 -6.0 -32.60 6.0 -31.40
foreach x {-4.08 0 4.08} {
    via_at via2 $x -32.0
}

# A contacted p-substrate guard ring surrounds the switching core.  Contacts
# are repeated at roughly 3--4 um pitch rather than relying on one remote tap.
paint_rect psubdiff -11.0 -37.0 -10.2 13.0
paint_rect psubdiff 10.2 -37.0 11.0 13.0
paint_rect psubdiff -11.0 -37.0 11.0 -36.2
paint_rect psubdiff -11.0 12.2 11.0 13.0
paint_rect metal1 -11.0 -37.0 -10.2 13.0
paint_rect metal1 10.2 -37.0 11.0 13.0
paint_rect metal1 -11.0 -37.0 11.0 -36.2
paint_rect metal1 -11.0 12.2 11.0 13.0
foreach x {-9 -6 -3 0 3 6 9} {
    substrate_contact $x -36.6
    substrate_contact $x 12.6
}
foreach y {-34 -30 -26 -22 -18 -14 -10 -6 -2 2 6 10} {
    substrate_contact -10.6 $y
    substrate_contact 10.6 $y
}

# Tie the guard ring directly to the tail-source VSS landing.
via_at via1 0 -36.6
paint_rect metal2 -0.60 -36.9 0.60 -31.4

# Cell interface.  Port ordering matches serdes_tx.spice.
make_port OUTP 3 metal3 -9.45 9.0 -8.55 12.0
make_port OUTN 4 metal3 8.55 9.0 9.45 12.0
make_port VDD 10 metal3 -1.0 49.45 1.0 50.55
make_port VSS 11 metal3 -1.0 -32.55 1.0 -31.45

save /work/serdes_tx
gds write /work/serdes_tx.gds
quit -noprompt
