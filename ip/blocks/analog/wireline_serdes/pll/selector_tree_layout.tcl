# SPDX-License-Identifier: Apache-2.0
# Balanced hierarchical selector tree built from fifteen high-gain selectors.

proc rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}

proc via_at {layer x y} {
    rect $layer [expr {$x-0.18}] [expr {$y-0.18}] \
        [expr {$x+0.18}] [expr {$y+0.18}]
}

proc transition_34 {x y} {
    rect metal3 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    via_at via3 $x $y
}

proc transition_45 {x y} {
    rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    rect metal5 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    via_at via4 $x $y
}

proc transition_35 {x y} {
    foreach layer {metal3 metal4 metal5} {
        rect $layer [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
    }
    via_at via3 $x $y
    via_at via4 $x $y
}

proc make_port {name number layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
    label $name FreeSans 0.5 0 0 0 c $layer
    port make $number
}

# Escape one child M3 output on M4, cross the inter-row channel on M4,
# and enter the parent M5 input.  Unique track heights prevent same-layer joins.
proc connect_clock {child_x child_y output_x parent_x parent_y input_x track_y} {
    set ox [expr {$child_x+$output_x}]
    set oy [expr {$child_y+14.25}]
    set escape_y [expr {$child_y+28.5}]
    set ix [expr {$parent_x+$input_x}]
    set iy [expr {$parent_y-26.4}]
    transition_34 $ox $oy
    rect metal4 [expr {$ox-0.38}] $oy [expr {$ox+0.38}] $escape_y
    transition_45 $ox $escape_y
    rect metal5 [expr {$ox-0.38}] $escape_y [expr {$ox+0.38}] $track_y
    transition_45 $ox $track_y
    rect metal4 [expr {min($ox,$ix)-0.38}] [expr {$track_y-0.38}] \
        [expr {max($ox,$ix)+0.38}] [expr {$track_y+0.38}]
    # Nearly aligned landings leave an illegal narrow M5 notch unless the two
    # same-net transition pads are merged on M5 as well.
    if {[expr {abs($ox-$ix)}] < 1.5} {
        rect metal5 [expr {min($ox,$ix)-0.38}] [expr {$track_y-0.38}] \
            [expr {max($ox,$ix)+0.38}] [expr {$track_y+0.38}]
    }
    transition_45 $ix $track_y
    rect metal5 [expr {$ix-0.38}] $track_y [expr {$ix+0.38}] $iy
}

proc connect_pair {left_x right_x child_y parent_x parent_y} {
    set base [expr {$child_y+31.0}]
    connect_clock $left_x $child_y 9.40 $parent_x $parent_y -27.0 $base
    connect_clock $left_x $child_y 20.60 $parent_x $parent_y -3.0 \
        [expr {$base+2.2}]
    connect_clock $right_x $child_y 9.40 $parent_x $parent_y -19.0 \
        [expr {$base+4.4}]
    connect_clock $right_x $child_y 20.60 $parent_x $parent_y -11.0 \
        [expr {$base+6.6}]
}

proc expose_controls {index cx cy first_port} {
    make_port S${index}A $first_port metal4 \
        [expr {$cx-34.0}] [expr {$cy-15.58}] \
        [expr {$cx-32.5}] [expr {$cy-14.82}]
    make_port S${index}B [expr {$first_port+1}] metal4 \
        [expr {$cx+25.5}] [expr {$cy-25.58}] \
        [expr {$cx+27.0}] [expr {$cy-24.82}]
    make_port S${index}BUF [expr {$first_port+2}] metal4 \
        [expr {$cx+25.5}] [expr {$cy-18.08}] \
        [expr {$cx+27.0}] [expr {$cy-17.32}]
}

crashbackups stop
load vco_selector_tree_hier
units microns

set placements {
    0 0.0 0.0 1 75.0 0.0 2 150.0 0.0 3 225.0 0.0
    4 300.0 0.0 5 375.0 0.0 6 450.0 0.0 7 525.0 0.0
    8 37.5 70.0 9 187.5 70.0 10 337.5 70.0 11 487.5 70.0
    12 112.5 140.0 13 412.5 140.0
    14 262.5 210.0
}
foreach {index x y} $placements {
    getcell vco_selector_unit child 0 0 parent $x $y
    identify X$index
}
select top cell
load vco_selector_tree_hier
units microns

# Twelve external differential leaves overlap the first six child input ports.
set port_number 1
for {set index 0} {$index < 12} {incr index} {
    set cell_index [expr {$index/2}]
    set cx [expr {$cell_index*75.0}]
    if {[expr {$index%2}] == 0} {
        set px [expr {$cx-27.0}]
        set nx [expr {$cx-3.0}]
    } else {
        set px [expr {$cx-19.0}]
        set nx [expr {$cx-11.0}]
    }
    make_port I${index}P $port_number metal5 \
        [expr {$px-0.45}] -27.0 [expr {$px+0.45}] -25.8
    incr port_number
    make_port I${index}N $port_number metal5 \
        [expr {$nx-0.45}] -27.0 [expr {$nx+0.45}] -25.8
    incr port_number
}

# Four unused leaves share one explicit quiet common-mode terminal.  The bus is
# on M4 and detours around the second child's all-metal VSS landing.
rect metal4 422.5 -27.2 488.3 -26.4
rect metal4 487.92 -29.4 488.68 -26.4
rect metal4 487.92 -29.4 491.08 -28.6
rect metal4 490.32 -29.4 491.08 -26.4
rect metal4 490.7 -27.2 553.0 -26.4
foreach x {423.0 431.0 439.0 447.0 498.0 506.0 514.0 522.0} {
    transition_45 $x -26.4
}
make_port VDUMMY 25 metal4 542.0 -27.2 553.0 -26.4

# Every selector control remains independently visible to the controller.
set control_port 26
foreach {index x y} $placements {
    expose_controls $index $x $y $control_port
    incr control_port 3
}

# Balanced inter-row clock routes.
connect_pair 0.0 75.0 0.0 37.5 70.0
connect_pair 150.0 225.0 0.0 187.5 70.0
connect_pair 300.0 375.0 0.0 337.5 70.0
connect_pair 450.0 525.0 0.0 487.5 70.0
connect_pair 37.5 187.5 70.0 112.5 140.0
connect_pair 337.5 487.5 70.0 412.5 140.0
connect_pair 112.5 412.5 140.0 262.5 210.0

# VDD escapes above each child on M3; VSS escapes below it.  Separate global
# spines keep both networks away from the M4/M5 clock channels.
foreach row_y {0.0 70.0 140.0 210.0} {
    set vdd_y [expr {$row_y+29.5}]
    set vss_y [expr {$row_y-31.5}]
    rect metal3 -45.5 [expr {$vdd_y-0.5}] 555.0 [expr {$vdd_y+0.5}]
    rect metal3 -35.5 [expr {$vss_y-0.5}] 565.5 [expr {$vss_y+0.5}]
}
foreach {index x y} $placements {
    set vx [expr {$x-4.0}]
    set vy [expr {$y+24.4}]
    transition_35 $vx $vy
    rect metal3 [expr {$vx-0.38}] $vy [expr {$vx+0.38}] [expr {$y+29.5}]
    set gx [expr {$x-35.5}]
    rect metal5 [expr {$gx-0.38}] [expr {$y-30.5}] \
        [expr {$gx+0.38}] [expr {$y-0.5}]
    transition_35 $gx [expr {$y-30.5}]
    rect metal3 [expr {$gx-0.38}] [expr {$y-31.5}] \
        [expr {$gx+0.38}] [expr {$y-30.5}]
}
rect metal3 -45.5 29.0 -44.5 240.0
rect metal3 564.5 -32.0 565.5 179.0
make_port VDD 71 metal3 -45.5 230.0 -44.5 240.0
make_port VSS 72 metal3 564.5 -32.0 565.5 -22.0

# Root output ports overlap the final child output shapes.
make_port OUTP 73 metal3 271.35 223.5 272.45 225.0
make_port OUTN 74 metal3 282.55 223.5 283.65 225.0

save vco_selector_tree
gds write /work/vco_selector_tree.gds
quit -noprompt
