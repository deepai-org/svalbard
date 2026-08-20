# SPDX-License-Identifier: Apache-2.0
# Minimum-geometry non-tileable GF180 3.3 V NAND2 density experiment.

proc rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}
proc make_port {name number layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    label $name FreeSans 0.25 0 0 0 c $layer
    port make $number
}
proc contact_pad {x y} {
    rect metal1 [expr {$x-0.18}] [expr {$y-0.20}] \
        [expr {$x+0.18}] [expr {$y+0.20}]
}
proc contact_pad_tall {x y half_height} {
    rect metal1 [expr {$x-0.18}] [expr {$y-$half_height}] \
        [expr {$x+0.18}] [expr {$y+$half_height}]
}
proc via1 {x y} {
    rect metal1 [expr {$x-0.19}] [expr {$y-0.19}] \
        [expr {$x+0.19}] [expr {$y+0.19}]
    rect via1 [expr {$x-0.13}] [expr {$y-0.13}] \
        [expr {$x+0.13}] [expr {$y+0.13}]
    rect metal2 [expr {$x-0.23}] [expr {$y-0.23}] \
        [expr {$x+0.23}] [expr {$y+0.23}]
}

crashbackups stop
set cell_name nand2_min_3v3
set wn 0.42
set wp 0.42
if {[info exists ::env(NAND_CELL)]} { set cell_name $::env(NAND_CELL) }
if {[info exists ::env(NAND_WN)]} { set wn $::env(NAND_WN) }
if {[info exists ::env(NAND_WP)]} { set wp $::env(NAND_WP) }
set n_half [expr {$wn/2.0}]
set p_half [expr {$wp/2.0}]
set n_y [expr {0.41+$n_half}]
set input_bottom [expr {0.63+$wn}]
set input_top [expr {$input_bottom+0.38}]
set input_center [expr {$input_bottom+0.19}]
set well_boundary [expr {0.84+$wn}]
set p_y [expr {$well_boundary+$p_half+0.65}]
set p_poly_bottom [expr {$p_y-$p_half-0.22}]
set n_contact_half [expr {max(0.20,$n_half-0.01)}]
set p_contact_half [expr {max(0.20,$p_half-0.01)}]
set vdd_bottom [expr {$p_y+$p_half+0.23}]
set cell_height [expr {$vdd_bottom+0.19}]
set nwell_top [expr {$p_y+$p_half+0.65}]
load ${cell_name}_hier
set nrow [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w $wn l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set prow [magic::gencell_makecell gf180mcu::pfet_03v3 \
    w $wp l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
units microns
getcell $nrow child 0 0 parent 0.98 $n_y
identify XNROW
getcell $prow child 0 0 parent 0.98 $p_y
identify XPROW
select top cell
flatten $cell_name
load $cell_name
units microns

# Standard-cell-like abutting well halves.  The generated PCell well enclosure
# deliberately extends beyond the 2.00 um logical cell width, as the reference
# library wells also extend beyond its placement boundary.
rect pwell -0.12 -0.19 2.08 $well_boundary
rect nwell -0.43 $well_boundary 2.39 $nwell_top

# Join each vertically aligned PMOS/NMOS gate in poly and contact it once in
# the quiet row gap.  Gate centers are x=0.60 (A1) and x=1.40 (A2).
foreach x {0.58 1.38} {
    rect polysilicon [expr {$x-0.14}] [expr {$n_y+$n_half}] \
        [expr {$x+0.14}] $p_poly_bottom
    rect polysilicon [expr {$x-0.18}] [expr {$input_bottom+0.01}] \
        [expr {$x+0.18}] [expr {$input_top-0.01}]
    rect polycontact [expr {$x-0.115}] [expr {$input_center-0.115}] \
        [expr {$x+0.115}] [expr {$input_center+0.115}]
    rect metal1 [expr {$x-0.19}] $input_bottom [expr {$x+0.19}] $input_top
}

# Enclose every diffusion contact with useful M1 area.  NMOS contact ordering
# is VSS, internal series node, output; PMOS ordering is VDD, output, VDD.
foreach x {0.18 0.98 1.78} {
    contact_pad_tall $x $n_y $n_contact_half
    contact_pad_tall $x $p_y $p_contact_half
}
# The uncontacted series node still needs a legal M1 landing area.
rect metal1 0.78 [expr {$n_y-0.20}] 1.18 [expr {$n_y+0.20}]

# Abutting supply rails and local connections.
rect metal1 0.00 -0.19 1.96 0.19
rect metal1 0.00 0.10 0.36 $n_y
rect metal1 0.00 $vdd_bottom 1.96 [expr {$cell_height+0.19}]
rect metal1 0.00 $p_y 0.36 $cell_height
rect metal1 1.60 $p_y 1.96 $cell_height

# Output uses M2 so it can pass the A2 M1 access without a short.
via1 0.98 $p_y
via1 1.71 $n_y
rect metal2 0.75 [expr {$p_y-0.23}] 1.94 [expr {$p_y+0.23}]
rect metal2 1.48 [expr {$n_y-0.23}] 1.94 [expr {$p_y+0.23}]

# Ports retain the reference cell order.  Body ports intentionally label the
# wells; a tile row supplies well taps separately, like the reference library.
make_port A1 1 metal1 0.39 $input_bottom 0.77 $input_top
make_port A2 2 metal1 1.19 $input_bottom 1.57 $input_top
make_port ZN 3 metal2 1.48 [expr {$p_y-0.53}] 1.94 [expr {$p_y-0.23}]
make_port VDD 4 metal1 0.00 $vdd_bottom 1.96 [expr {$cell_height+0.19}]
make_port VNW 5 nwell -0.32 [expr {$nwell_top-0.50}] 0.08 [expr {$nwell_top-0.10}]
make_port VPW 6 pwell -0.05 -0.18 0.35 0.18
make_port VSS 7 metal1 0.00 -0.19 1.96 0.19

property FIXED_BBOX 0 0 1.96 $cell_height
box values -1.0 -1.0 3.0 3.5
drc check
drc catchup
puts "CUSTOM_DRC_COUNT [drc list count total]"
save $cell_name
gds write /work/${cell_name}.gds
quit -noprompt
