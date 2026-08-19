# SPDX-License-Identifier: Apache-2.0
# Hierarchical physical ring VCO with matched deterministic startup assist.

proc band_rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}

proc band_via {layer x y} {
    band_rect $layer [expr {$x-0.18}] [expr {$y-0.18}] \
        [expr {$x+0.18}] [expr {$y+0.18}]
}

proc band_transition_34 {x y} {
    foreach layer {metal3 metal4} {
        band_rect $layer [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
    }
    band_via via3 $x $y
}

proc band_transition_35 {x y} {
    foreach layer {metal3 metal4 metal5} {
        band_rect $layer [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
    }
    band_via via3 $x $y
    band_via via4 $x $y
}

proc band_transition_45 {x y} {
    foreach layer {metal4 metal5} {
        band_rect $layer [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
    }
    band_via via4 $x $y
}

proc band_port {name number layer x1 y1 x2 y2} {
    band_rect $layer $x1 $y1 $x2 $y2
    box values $x1 $y1 $x2 $y2
    label $name FreeSans 0.5 0 0 0 c $layer
    port make $number
}

# Route one polarity from a child M3 output to a child M5 input below the row.
# M5 owns the vertical escapes while M4 owns the horizontal channel.  This is
# intentional: a row-level ring has nested feedback paths, so same-layer
# vertical drops would short every horizontal track they cross.
proc band_clock {source_x target_x xoff track_y} {
    set ox [expr {$source_x+$xoff}]
    set oy 1.50
    set escape_x [expr {$source_x+($xoff < 0 ? -30.0 : 30.0)}]
    set ix [expr {$target_x+$xoff}]
    set iy -21.40
    band_transition_35 $ox $oy
    band_rect metal5 [expr {min($ox,$escape_x)-0.38}] [expr {$oy-0.38}] \
        [expr {max($ox,$escape_x)+0.38}] [expr {$oy+0.38}]
    band_rect metal5 [expr {$escape_x-0.38}] $track_y \
        [expr {$escape_x+0.38}] [expr {$oy+0.38}]
    band_transition_45 $escape_x $track_y
    band_rect metal4 [expr {min($escape_x,$ix)-0.38}] [expr {$track_y-0.38}] \
        [expr {max($escape_x,$ix)+0.38}] [expr {$track_y+0.38}]
    band_transition_45 $ix $track_y
    band_rect metal5 [expr {$ix-0.38}] $track_y \
        [expr {$ix+0.38}] $iy
}

proc band_pair {source_x target_x p_track n_track} {
    band_clock $source_x $target_x -15.0 $p_track
    band_clock $source_x $target_x 15.0 $n_track
}

# Route a mirrored differential pair between vertically stacked children.
# Both source escapes move outward on M4, descend or rise outside every child
# guard ring on M5, and return on M4 in the target-side gap.  No high-speed
# conductor crosses an active-cell interior.
proc band_pair_column {source_y target_y escape_abs track_y} {
    foreach {xoff sign} {-15.0 -1.0 15.0 1.0} {
        set ox $xoff
        set oy [expr {$source_y+1.50}]
        set ix $xoff
        set iy [expr {$target_y-21.40}]
        set escape_x [expr {$sign*$escape_abs}]
        band_transition_34 $ox $oy
        band_rect metal4 [expr {min($ox,$escape_x)-0.38}] \
            [expr {$oy-0.38}] [expr {max($ox,$escape_x)+0.38}] \
            [expr {$oy+0.38}]
        band_transition_45 $escape_x $oy
        band_rect metal5 [expr {$escape_x-0.38}] \
            [expr {min($oy,$track_y)-0.38}] [expr {$escape_x+0.38}] \
            [expr {max($oy,$track_y)+0.38}]
        band_transition_45 $escape_x $track_y
        band_rect metal4 [expr {min($escape_x,$ix)-0.38}] \
            [expr {$track_y-0.38}] [expr {max($escape_x,$ix)+0.38}] \
            [expr {$track_y+0.38}]
        band_transition_45 $ix $track_y
        band_rect metal5 [expr {$ix-0.38}] \
            [expr {min($track_y,$iy)-0.38}] [expr {$ix+0.38}] \
            [expr {max($track_y,$iy)+0.38}]
    }
}

crashbackups stop
set band_cell_name cml_vco_band
if {[info exists ::env(VCO_BAND_CELL_NAME)]} {
    set band_cell_name $::env(VCO_BAND_CELL_NAME)
}
load ${band_cell_name}_hier
units microns
set band_delay_cell cml_vco_delay_margin_fast
if {[info exists ::env(VCO_BAND_DELAY_CELL)]} {
    set band_delay_cell $::env(VCO_BAND_DELAY_CELL)
}
set band_route_style column
if {[info exists ::env(VCO_BAND_ROUTE_STYLE)]} {
    set band_route_style $::env(VCO_BAND_ROUTE_STYLE)
}
set band_pitch 64.0
set band_main_tail_w 15.0
set band_latch_tail_w 6.0
set band_split_control 0
if {[info exists ::env(VCO_MAIN_TAIL_W)]} {
    set band_main_tail_w $::env(VCO_MAIN_TAIL_W)
}
if {[info exists ::env(VCO_LATCH_TAIL_W)]} {
    set band_latch_tail_w $::env(VCO_LATCH_TAIL_W)
}
if {[info exists ::env(VCO_SPLIT_CONTROL)]} {
    set band_split_control $::env(VCO_SPLIT_CONTROL)
}
if {$band_route_style == "legacy" && $band_split_control} {
    error "split tail control is supported only by the folded column parent"
}
if {$band_route_style == "legacy"} {
    set placements [list \
        X0 0 0 $band_delay_cell \
        X1 70 0 $band_delay_cell \
        X2 140 0 $band_delay_cell \
        XBUF 210 0 $band_delay_cell \
        XSTART 0 45 cml_vco_startup_assist]
} else {
    set placements [list \
        X0 0 0 $band_delay_cell \
        X1 0 $band_pitch $band_delay_cell \
        X2 0 [expr {2.0*$band_pitch}] $band_delay_cell \
        XBUF 0 [expr {3.0*$band_pitch}] $band_delay_cell \
        XSTART 0 -45 cml_vco_startup_assist]
}
foreach {instance x y cell} $placements {
    getcell $cell child 0 0 parent $x $y
    identify $instance
}
select top cell
load ${band_cell_name}_hier
units microns

# Three-stage odd ring and isolated buffer.  The column route keeps all
# differential geometry mirror-symmetric and outside child interiors.  The
# legacy row remains selectable for controlled extraction comparisons.
if {$band_route_style == "legacy"} {
    band_pair 0 70 -30.0 -32.2
    band_pair 70 140 -34.4 -36.6
    band_pair 140 0 -38.8 -41.0
    band_pair 140 210 -43.2 -45.4
} else {
    band_pair_column 0 $band_pitch 29.0 [expr {$band_pitch-28.0}]
    band_pair_column $band_pitch [expr {2.0*$band_pitch}] 29.0 \
        [expr {2.0*$band_pitch-28.0}]
    band_pair_column [expr {2.0*$band_pitch}] 0 33.0 -28.0
    band_pair_column [expr {2.0*$band_pitch}] \
        [expr {3.0*$band_pitch}] 29.0 \
        [expr {3.0*$band_pitch-28.0}]
}

# Startup drains escape outward, avoiding every internal child route.  They
# attach to the first stage's output nodes on matched paths.
if {$band_route_style == "legacy"} {
    band_transition_34 -15 1.50
    band_rect metal4 -31.0 1.12 -14.62 1.88
    band_rect metal4 -31.0 1.12 -30.24 46.0
    band_rect metal4 -31.0 45.62 -9.25 46.38
    band_transition_34 15 1.50
    band_rect metal4 14.62 1.12 31.0 1.88
    band_rect metal4 30.24 1.12 31.0 46.0
    band_rect metal4 9.25 45.62 31.0 46.38
} else {
    foreach {sign node_x escape_x output_x} \
            {-1.0 -9.25 -35.0 -15.0 1.0 9.25 35.0 15.0} {
        set startup_y -44.0
        band_rect metal4 [expr {min($node_x,$escape_x)-0.38}] \
            [expr {$startup_y-0.38}] \
            [expr {max($node_x,$escape_x)+0.38}] \
            [expr {$startup_y+0.38}]
        band_transition_45 $escape_x $startup_y
        band_rect metal5 [expr {$escape_x-0.38}] \
            [expr {$startup_y-0.38}] [expr {$escape_x+0.38}] 1.88
        band_transition_45 $escape_x 1.50
        band_rect metal4 [expr {min($escape_x,$output_x)-0.38}] 1.12 \
            [expr {max($escape_x,$output_x)+0.38}] 1.88
        band_transition_34 $output_x 1.50
    }
}

# Common supplies and controls use separate crossing-safe spines.
if {$band_route_style == "legacy"} {
    set band_x2 140.0
    set band_xbuf 210.0
    band_rect metal5 -1.0 24.70 211.0 27.00
    band_port VDD 4 metal5 102.0 24.70 108.0 27.00
    band_rect metal4 -24.0 -19.08 218.5 -18.32
    band_port VCTRL 1 metal4 212.0 -19.08 218.5 -18.32
    band_rect metal3 -27.0 -25.90 237.0 -25.10
    foreach x {-26.5 43.5 113.5 183.5} {
        band_transition_35 $x -21.50
        foreach layer {metal4 metal5} {
            band_rect $layer [expr {$x-0.38}] -22.50 \
                [expr {$x+0.38}] -21.50
        }
        band_rect metal3 [expr {$x-0.38}] -25.90 \
            [expr {$x+0.38}] -21.50
    }
    band_rect metal3 -0.38 -25.90 0.38 43.60
    band_port VSS 5 metal3 -27.0 -25.90 -20.0 -25.10
    band_port KICKP 2 metal4 -4.45 38.50 -3.55 39.80
    band_port KICKN 3 metal4 3.55 38.50 4.45 39.80
    band_port CLK_P 6 metal3 194.0 1.05 197.5 1.95
    band_port CLK_N 7 metal3 222.5 1.05 226.2 1.95
} else {
    set band_ybuf [expr {3.0*$band_pitch}]
    set band_vctrl_y [expr {-13.70-$band_main_tail_w/2.0}]
    set band_regen_y [expr {-13.70-$band_latch_tail_w/2.0}]

    # M4 VDD spine at the far left; each horizontal branch meets the child's
    # central M5 rail through one deliberate transition.
    band_rect metal4 -42.38 26.92 -41.62 [expr {$band_ybuf+27.68}]
    foreach y [list 0 $band_pitch [expr {2.0*$band_pitch}] $band_ybuf] {
        set rail_y [expr {$y+27.3}]
        band_rect metal4 -42.38 [expr {$rail_y-0.38}] 0.38 \
            [expr {$rail_y+0.38}]
        band_transition_45 0 $rail_y
    }
    band_port VDD 4 metal4 -42.45 [expr {$band_pitch+24.0}] \
        -41.55 [expr {$band_pitch+30.0}]

    # M5 main-tail-control spine at the far right.  Its M4 branches cross the
    # signal M5 escapes without vias and meet each child's gate conductor.
    band_rect metal5 41.62 $band_vctrl_y 42.38 \
        [expr {$band_ybuf+$band_vctrl_y+0.38}]
    foreach y [list 0 $band_pitch [expr {2.0*$band_pitch}] $band_ybuf] {
        set control_y [expr {$y+$band_vctrl_y}]
        set control_start [expr {$band_split_control ? -8.38 : 7.62}]
        band_rect metal4 $control_start [expr {$control_y-0.38}] 42.38 \
            [expr {$control_y+0.38}]
        band_transition_45 42.0 $control_y
    }
    set main_control_name [expr {$band_split_control ? "VCTRL_MAIN" : "VCTRL"}]
    band_port $main_control_name 1 metal5 41.55 \
        [expr {$band_pitch+$band_vctrl_y-3.0}] \
        42.45 [expr {$band_pitch+$band_vctrl_y+3.0}]

    if {$band_split_control} {
        # A second quiet spine independently biases the regenerative tails.
        # M4 branches overlap the child's right-side VCTRL_REGEN landing.
        band_rect metal5 36.62 $band_regen_y 37.38 \
            [expr {$band_ybuf+$band_regen_y+0.38}]
        foreach y [list 0 $band_pitch [expr {2.0*$band_pitch}] $band_ybuf] {
            set regen_y [expr {$y+$band_regen_y}]
            band_rect metal4 7.62 [expr {$regen_y-0.38}] 37.38 \
                [expr {$regen_y+0.38}]
            band_transition_45 37.0 $regen_y
        }
        band_port VCTRL_REGEN 8 metal5 36.55 \
            [expr {$band_pitch+$band_regen_y-3.0}] 37.45 \
            [expr {$band_pitch+$band_regen_y+3.0}]
    }

    # M3 VSS spine at the far right.  Each branch reaches the child's physical
    # VSS landing; startup VSS joins on its own M3 branch below X0.
    band_rect metal3 46.62 -46.78 47.38 \
        [expr {$band_ybuf-21.12}]
    foreach y [list 0 $band_pitch [expr {2.0*$band_pitch}] $band_ybuf] {
        set landing_y [expr {$y-21.50}]
        set branch_y [expr {$y-25.50}]
        band_transition_35 -26.5 $landing_y
        foreach layer {metal4 metal5} {
            band_rect $layer -26.88 [expr {$landing_y-1.0}] \
                -26.12 [expr {$landing_y+0.38}]
        }
        band_rect metal3 -26.88 [expr {$branch_y-0.38}] \
            -26.12 [expr {$landing_y+0.38}]
        band_rect metal3 -26.88 [expr {$branch_y-0.38}] 47.38 \
            [expr {$branch_y+0.38}]
    }
    band_rect metal3 -0.38 -46.78 47.38 -46.02
    band_port VSS 5 metal3 46.55 -29.0 47.45 -23.0

    band_port KICKP 2 metal4 -4.45 -51.50 -3.55 -50.20
    band_port KICKN 3 metal4 3.55 -51.50 4.45 -50.20
    band_port CLK_P 6 metal3 -16.2 [expr {$band_ybuf+1.05}] \
        -12.5 [expr {$band_ybuf+1.95}]
    band_port CLK_N 7 metal3 12.5 [expr {$band_ybuf+1.05}] \
        16.2 [expr {$band_ybuf+1.95}]
}

save $band_cell_name
gds write /work/${band_cell_name}.gds
quit -noprompt
