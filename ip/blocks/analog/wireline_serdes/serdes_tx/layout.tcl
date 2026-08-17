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

proc manual_gate {cx y half_width name port_number} {
    paint_rect polysilicon [expr {$cx-$half_width}] $y \
        [expr {$cx+$half_width}] [expr {$y+0.25}]
    paint_rect polysilicon [expr {$cx-0.20}] $y \
        [expr {$cx+0.20}] [expr {$y+0.90}]
    paint_rect polycontact [expr {$cx-0.115}] [expr {$y+0.585}] \
        [expr {$cx+0.115}] [expr {$y+0.815}]
    paint_rect metal1 [expr {$cx-0.35}] [expr {$y+0.40}] \
        [expr {$cx+0.35}] [expr {$y+1.00}]
    make_port $name $port_number metal1 [expr {$cx-0.30}] [expr {$y+0.45}] \
        [expr {$cx+0.30}] [expr {$y+0.95}]
}

crashbackups stop
load serdes_tx_hier

set diff_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 20 l 0.28 nf 10 guard 0 topc 0 botc 0 full_metal 0]
set tail_cell [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w 20 l 0.5 nf 10 guard 0 topc 0 botc 0 full_metal 0]
set load_cell [magic::gencell_makecell gf180mcu::ppolyf_s \
    w 1 l 14.3 guard 1 full_metal 1]

units microns
foreach {cell instance x y} [list \
        $diff_cell MDIFF_P -14 0 \
        $diff_cell MDIFF_N 14 0 \
        $tail_cell MTAIL 0 -52 \
        $load_cell RLOAD_P -14 50 \
        $load_cell RLOAD_N 14 50] {
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

# One continuous p-well joins every NMOS body, both resistor shields, and the tap.
paint_rect pwell -21.0 -67.1 21.0 59.0

# Poly straps join the fingers; one deliberately placed contact owns each gate pin.
manual_gate -14 10.10 3.75 INP 1
manual_gate 14 10.10 3.75 INN 2
manual_gate 0 -41.90 4.82 VBIAS 5

# Alternate diffusion bars are collected on metal2 at opposite ends.
set even_diff {-4.0 -2.4 -0.8 0.8 2.4 4.0}
set odd_diff {-3.2 -1.6 0.0 1.6 3.2}
set even_tail {-5.1 -3.06 -1.02 1.02 3.06 5.1}
set odd_tail {-4.08 -2.04 0.0 2.04 4.08}
mos_terminal_strap -14 0 8.0 $even_diff
mos_terminal_strap -14 0 -8.0 $odd_diff
mos_terminal_strap 14 0 8.0 $even_diff
mos_terminal_strap 14 0 -8.0 $odd_diff
mos_terminal_strap 0 -52 8.0 $even_tail
mos_terminal_strap 0 -52 -8.0 $odd_tail

# Common-source node from the differential pair to the tail device drain.
paint_rect metal2 -20.8 -8.38 20.8 -7.62
paint_rect metal2 -0.38 -44.0 0.38 -8.0

# Resistor terminal landing pads and vias.
foreach x {-14 14} {
    foreach y {42.67 57.33} {
        paint_rect metal1 [expr {$x-0.60}] [expr {$y-0.25}] \
            [expr {$x+0.60}] [expr {$y+0.25}]
        via_at via1 $x $y
        paint_rect metal2 [expr {$x-0.45}] [expr {$y-0.45}] \
            [expr {$x+0.45}] [expr {$y+0.45}]
    }
}

# VDD joins the upper load terminals.  OUTP/OUTN run vertically on metal3.
paint_rect metal2 -14.4 56.95 14.4 57.71
foreach x {-14 14} {
    via_at via2 $x 8.0
    via_at via2 $x 42.67
    paint_rect metal3 [expr {$x-0.55}] 7.60 [expr {$x+0.55}] 43.10
}

# The tail source is the local VSS landing rail.
paint_rect metal2 -6.8 -60.38 6.8 -59.62

# A dedicated p-substrate tap establishes the bulk connection for all devices.
paint_rect psubdiff -1.1 -66.9 -0.4 -66.1
paint_rect metal1 -1.1 -66.9 0.6 -66.1
paint_rect psubdiffcont -1.0 -66.8 -0.5 -66.2
via_at via1 0.0 -66.5
paint_rect metal2 -0.40 -66.8 0.40 -60.0

# Cell interface.  Port ordering matches serdes_tx.spice.
make_port OUTP 3 metal3 -14.38 20.0 -13.62 23.0
make_port OUTN 4 metal3 13.62 20.0 14.38 23.0
make_port VDD 6 metal2 -1.0 56.95 1.0 57.71
make_port VSS 7 metal2 -1.0 -60.38 1.0 -59.62

save /work/serdes_tx
gds write /work/serdes_tx.gds
quit -noprompt
