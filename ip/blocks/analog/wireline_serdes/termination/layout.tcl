# SPDX-License-Identifier: Apache-2.0
# GF180 layout for the programmable differential termination.

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
    }
    if {$highest >= 4} {
        paint_rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
    }
    if {$highest >= 5} {
        paint_rect metal5 [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
    }
    via_at via1 $x $y
    if {$highest >= 3} { via_at via2 $x $y }
    if {$highest >= 4} { via_at via3 $x $y }
    if {$highest >= 5} { via_at via4 $x $y }
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
    paint_rect metal2 [expr {$cx+[lindex $xs 0]-0.35}] [expr {$y-0.35}] \
        [expr {$cx+[lindex $xs end]+0.35}] [expr {$y+0.35}]
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
load serdes_termination_hier

set base_cell [magic::gencell_makecell gf180mcu::ppolyf_u \
    w 4 l 1.23 guard 1 full_metal 1]
set fine_cell [magic::gencell_makecell gf180mcu::ppolyf_u \
    w 1 l 2.43 guard 1 full_metal 1]
set coarse_cell [magic::gencell_makecell gf180mcu::ppolyf_u \
    w 1 l 1.0 guard 1 full_metal 1]
set pass_n [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 10 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set pass_p [magic::gencell_makecell gf180mcu::pfet_03v3 \
    w 10 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set inv_n [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 1 l 0.28 nf 1 guard 0 topc 0 botc 0 full_metal 0]
set inv_p [magic::gencell_makecell gf180mcu::pfet_03v3 \
    w 2 l 0.28 nf 1 guard 0 topc 0 botc 0 full_metal 0]

units microns
set branch_x {-27 -18 -9 0 9 18 27}
set idx 0
foreach x $branch_x {
    if {$idx < 2} { set resistor_cell $fine_cell } else { set resistor_cell $coarse_cell }
    getcell $resistor_cell child 0 0 parent $x 16
    identify RTRIM${idx}P
    getcell $resistor_cell child 0 0 parent $x -16
    identify RTRIM${idx}N
    getcell $pass_p child 0 0 parent $x 6
    identify XSW${idx}
    getcell $pass_n child 0 0 parent $x -6
    identify XNSW${idx}
    getcell $inv_p child 0 0 parent $x 32
    identify XPINV${idx}
    getcell $inv_n child 0 0 parent $x 28
    identify XNINV${idx}
    incr idx
}
getcell $base_cell child 0 0 parent 36 0
identify XBASE

select top cell
flatten serdes_termination
load serdes_termination
units microns

# Explicit device wells.  The signal PMOS and inverter PMOS rows have separate
# contacted wells; the resistor/NMOS region shares a continuous p-well.
paint_rect pwell -34 -25 42 25
paint_rect pwell -34 25 34 30
paint_rect nwell -32 0 32 12.8
paint_rect nwell -32 30 32 36.5

# Pass-device diffusion collection.  PMOS and NMOS outer bars form P<i>;
# their center bars form N<i>.  These two nodes stay on opposite sides of each
# midpoint transmission gate and never cross the high-speed input buses.
foreach x $branch_x {
    mos_terminal_strap $x 6 4.0 {-0.8 0.8}
    mos_terminal_strap $x 6 -4.0 {0.0}
    mos_terminal_strap $x -6 4.0 {-0.8 0.8}
    mos_terminal_strap $x -6 -4.0 {0.0}
    manual_gate_top $x 11.10 0.55 {-0.4 0.4}
    manual_gate_bottom $x -11.35 0.55 {-0.4 0.4}

    foreach {node_x y1 y2} [list [expr {$x-1.6}] -2.35 14.5 \
                                      [expr {$x+1.6}] -14.5 2.35] {
        paint_rect metal3 [expr {$node_x-0.38}] $y1 [expr {$node_x+0.38}] $y2
    }
    foreach {vx vy} [list [expr {$x-0.8}] 10.0 [expr {$x-0.8}] -2.0 \
                               $x 2.0 $x -10.0] {
        via_at via2 $vx $vy
        paint_rect metal3 [expr {$vx-0.34}] [expr {$vy-0.34}] \
            [expr {$vx+0.34}] [expr {$vy+0.34}]
    }
    paint_rect metal3 [expr {$x-1.98}] 9.62 [expr {$x-0.42}] 10.38
    paint_rect metal3 [expr {$x-1.98}] -2.38 [expr {$x-0.42}] -1.62
    paint_rect metal3 $x 1.62 [expr {$x+1.98}] 2.38
    paint_rect metal3 $x -10.38 [expr {$x+1.98}] -9.62
}

# Resistor terminals and short branch connections.  These offsets address the
# inner resistor contacts, not the outer grounded guard-ring metal.
set idx 0
foreach x $branch_x {
    if {$idx < 2} { set roff 1.545 } else { set roff 0.830 }
    foreach y [list [expr {16+$roff}] [expr {16-$roff}] \
                         [expr {-16+$roff}] [expr {-16-$roff}]] {
        paint_rect metal1 [expr {$x-0.30}] [expr {$y-0.30}] \
            [expr {$x+0.30}] [expr {$y+0.30}]
        via_at via1 $x $y
        via_at via2 $x $y
        paint_rect metal2 [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
        paint_rect metal3 [expr {$x-0.45}] [expr {$y-0.38}] \
            [expr {$x+0.45}] [expr {$y+0.38}]
    }
    paint_rect metal3 [expr {$x-0.38}] [expr {16-$roff-0.38}] \
        [expr {$x+0.38}] 14.5
    paint_rect metal3 [expr {$x-0.38}] -14.5 \
        [expr {$x+0.38}] [expr {-16+$roff+0.38}]
    paint_rect metal3 [expr {$x-1.98}] 14.12 [expr {$x+0.45}] 14.88
    paint_rect metal3 [expr {$x-0.45}] -14.88 [expr {$x+1.98}] -14.12
    paint_rect metal3 [expr {$x-0.38}] [expr {16+$roff-0.38}] \
        [expr {$x+0.38}] 20.5
    paint_rect metal3 [expr {$x-0.38}] -20.5 \
        [expr {$x+0.38}] [expr {-16-$roff+0.38}]
    incr idx
}

# Base resistor lands directly between matched metal3 input buses.
foreach y {-0.945 0.945} {
    paint_rect metal1 35.65 [expr {$y-0.30}] 36.35 [expr {$y+0.30}]
    via_at via1 36 $y
    via_at via2 36 $y
    paint_rect metal2 35.62 [expr {$y-0.38}] 36.38 [expr {$y+0.38}]
}
paint_rect metal3 35.55 0.60 36.45 20.5
paint_rect metal3 35.55 -20.5 36.45 -0.60

paint_rect metal3 -29 19.5 37 20.5
paint_rect metal3 -29 -20.5 37 -19.5
make_port RXP 1 metal3 -2.0 19.5 2.0 20.5
make_port RXN 2 metal3 -2.0 -20.5 2.0 -19.5

# Local inverters generate active-high NMOS controls from active-low pins.
# The inverter output rises to metal5 before crossing either signal bus.
set idx 0
foreach x $branch_x {
    manual_gate_top $x 33.10 0.22 {0.0}
    manual_gate_bottom $x 27.15 0.22 {0.0}

    # PMOS/NMOS inverter sources.
    foreach {sx sy} [list [expr {$x-0.4}] 32 [expr {$x-0.4}] 28] {
        paint_rect metal1 [expr {$sx-0.28}] [expr {$sy-0.28}] \
            [expr {$sx+0.28}] [expr {$sy+0.28}]
        via_at via1 $sx $sy
        paint_rect metal2 [expr {$x-2.38}] [expr {$sy-0.38}] \
            [expr {$sx+0.19}] [expr {$sy+0.38}]
        via_at via2 [expr {$x-2.0}] $sy
        paint_rect metal3 [expr {$x-2.38}] [expr {$sy-0.38}] \
            [expr {$x-1.62}] [expr {$sy+0.38}]
        if {$sy > 30} {
            paint_rect metal3 [expr {$x-2.35}] 31.65 [expr {$x-1.65}] 35.45
        } else {
            paint_rect metal3 [expr {$x-2.35}] 24.55 [expr {$x-1.65}] 28.35
        }
    }
    # Joined inverter drains.
    foreach sy {28 32} {
        set dx [expr {$x+0.4}]
        paint_rect metal1 [expr {$dx-0.28}] [expr {$sy-0.28}] \
            [expr {$dx+0.28}] [expr {$sy+0.28}]
        via_at via1 $dx $sy
        paint_rect metal2 [expr {$dx-0.24}] [expr {$sy-0.38}] \
            [expr {$x+2.38}] [expr {$sy+0.38}]
        via_at via2 [expr {$x+2.0}] $sy
        paint_rect metal3 [expr {$x+1.62}] [expr {$sy-0.38}] \
            [expr {$x+2.38}] [expr {$sy+0.38}]
    }
    paint_rect metal3 [expr {$x+1.62}] 27.65 [expr {$x+2.38}] 32.35
    paint_rect metal3 [expr {$x+1.62}] 29.65 [expr {$x+3.58}] 30.35
    stack_to [expr {$x+3.2}] 30 5
    paint_rect metal5 [expr {$x+2.85}] -12.0 [expr {$x+3.55}] 30.35

    # NMOS pass gate access to the inverter output.
    paint_rect metal1 [expr {$x-0.75}] -12.0 [expr {$x+0.75}] -11.35
    paint_rect metal2 [expr {$x-0.75}] -12.0 [expr {$x+0.75}] -11.35
    paint_rect metal3 [expr {$x-0.75}] -12.0 [expr {$x+0.75}] -11.35
    paint_rect metal4 [expr {$x-0.75}] -12.0 [expr {$x+0.75}] -11.35
    paint_rect metal5 [expr {$x-0.75}] -12.0 [expr {$x+3.55}] -11.35
    stack_to $x -11.65 5

    # Active-low input joins the PMOS pass gate and both inverter gates on M4.
    foreach gy [list 11.65 26.80 33.65] {
        paint_rect metal1 [expr {$x-0.75}] [expr {$gy-0.35}] \
            [expr {$x+0.75}] [expr {$gy+0.35}]
        paint_rect metal2 [expr {$x-0.75}] [expr {$gy-0.35}] \
            [expr {$x+0.75}] [expr {$gy+0.35}]
        paint_rect metal3 [expr {$x-0.75}] [expr {$gy-0.35}] \
            [expr {$x+0.75}] [expr {$gy+0.35}]
        paint_rect metal4 [expr {$x-0.75}] [expr {$gy-0.35}] \
            [expr {$x+0.75}] [expr {$gy+0.35}]
        stack_to $x $gy 4
    }
    paint_rect metal4 [expr {$x-0.35}] 11.3 [expr {$x+0.35}] 38.0
    make_port TERM_EN${idx}_N [expr {3+$idx}] metal4 \
        [expr {$x-0.35}] 37.0 [expr {$x+0.35}] 38.0
    incr idx
}

# Inverter supply rails.
paint_rect metal3 -30 34.55 39.5 35.45
paint_rect metal3 -31.5 24.55 30 25.45

# Repeated n-well taps tie both PMOS rows to VDD.
foreach x $branch_x {
    set tapx [expr {$x-3.0}]
    paint_rect nsubdiff [expr {$tapx-0.35}] 34.62 [expr {$tapx+0.35}] 35.38
    nwell_contact $tapx 35.0
    paint_rect metal1 [expr {$tapx-0.38}] 34.62 [expr {$tapx+0.38}] 35.38
    via_at via1 $tapx 35.0
    via_at via2 $tapx 35.0
    paint_rect metal2 [expr {$tapx-0.38}] 34.62 [expr {$tapx+0.38}] 35.38
    paint_rect metal3 [expr {$tapx-0.38}] 34.62 [expr {$tapx+0.38}] 35.38
}
foreach tapx {31} {
    paint_rect nsubdiff [expr {$tapx-0.35}] 5.62 [expr {$tapx+0.35}] 6.38
    nwell_contact $tapx 6.0
    paint_rect metal1 [expr {$tapx-0.38}] 5.62 [expr {$tapx+0.38}] 6.38
    via_at via1 $tapx 6.0
}
paint_rect metal2 30.62 5.55 39.5 6.45
stack_to 39 6.0 5
stack_to 39 35.0 5
paint_rect metal5 38.55 5.65 39.45 37.0
paint_rect metal5 -30 36.0 39.45 37.0
make_port VDD 10 metal5 -1.0 36.0 1.0 37.0

# Contacted substrate guard and VSS connection.
paint_rect psubdiff -33 -24 -32.2 39
paint_rect psubdiff 40.2 -24 41 39
paint_rect psubdiff -33 -24 41 -23.2
paint_rect psubdiff -33 38.2 41 39
paint_rect metal1 -33 -24 -32.2 39
paint_rect metal1 40.2 -24 41 39
paint_rect metal1 -33 -24 41 -23.2
paint_rect metal1 -33 38.2 41 39
foreach x {-30 -24 -18 -12 -6 0 6 12 18 24 30 36} {
    substrate_contact $x -23.6
    substrate_contact $x 38.6
}
foreach y {-20 -14 -8 -2 4 10 16 22 28 34} {
    substrate_contact -32.6 $y
    substrate_contact 40.6 $y
}
stack_to -31 25.0 5
paint_rect metal5 -31.45 -23.9 -30.55 25.45
paint_rect metal2 -32.9 -23.9 -28.6 -23.3
via_at via1 -32.6 -23.6
stack_to -31 -23.6 5
make_port VSS 11 metal5 -31.45 -1.0 -30.55 1.0

save /work/serdes_termination
gds write /work/serdes_termination.gds
quit -noprompt
