# SPDX-License-Identifier: Apache-2.0
# Two vertically composed, independently guarded wideband data stages.

proc paint_rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}
proc via_at {layer x y} {
    paint_rect $layer [expr {$x-0.18}] [expr {$y-0.18}] \
        [expr {$x+0.18}] [expr {$y+0.18}]
}
proc make_port {name number layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    label $name FreeSans 0.5 0 0 0 c $layer
    port make $number
}

crashbackups stop
load cml_data_restorer_hier
units microns
getcell cml_data_restorer_stage child 0 0 parent 0 0
identify XPRE
getcell cml_data_restorer_stage child 0 0 parent 0 47
identify XDRV
select top cell
flatten cml_data_restorer
load cml_data_restorer
units microns

# Child pin labels are implementation details at this flattened boundary.
box values -20 -25 20 73
erase labels

# PRE outputs rise to M4, detour around the PRE load-to-VDD stacks, and meet
# the DRV input pair only at its bottom M5 ports.
foreach x {-4 4} {
    set escape_x [expr {$x < 0 ? -6 : 6}]
    paint_rect metal3 [expr {$x-0.38}] 10.0 [expr {$x+0.38}] 10.76
    via_at via3 $x 10.38
    paint_rect metal4 [expr {min($x,$escape_x)-0.38}] 10.0 \
        [expr {max($x,$escape_x)+0.38}] 10.76
    paint_rect metal4 [expr {$escape_x-0.38}] 10.0 \
        [expr {$escape_x+0.38}] 27.76
    paint_rect metal4 [expr {min($x,$escape_x)-0.38}] 27.0 \
        [expr {max($x,$escape_x)+0.38}] 27.76
    via_at via4 $x 27.38
    paint_rect metal5 [expr {$x-0.38}] 27.0 [expr {$x+0.38}] 27.76
}

# Shared supplies and bias use parent-owned spines outside sensitive nodes.
paint_rect metal5 8.9 21.1 9.8 69.0
paint_rect metal5 -13.95 1.5 -13.05 49.0
paint_rect metal4 -0.38 -19.0 0.38 29.7

make_port IN_P 1 metal5 -4.45 -20.0 -3.55 -18.8
make_port IN_N 2 metal5 3.55 -20.0 4.45 -18.8
make_port VBIAS 3 metal4 -0.45 -20.0 0.45 -18.8
make_port VDD 4 metal5 8.9 68.1 9.8 69.0
make_port VSS 5 metal5 -13.95 -2.0 -13.05 0.0
make_port OUT_P 6 metal3 -4.45 56.5 -3.55 58.0
make_port OUT_N 7 metal3 3.55 56.5 4.45 58.0

save /work/cml_data_restorer
gds write /work/cml_data_restorer.gds
quit -noprompt
