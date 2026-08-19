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

crashbackups stop
load cml_vco_band_hier
units microns
set band_delay_cell cml_vco_delay_margin_fast
if {[info exists ::env(VCO_BAND_DELAY_CELL)]} {
    set band_delay_cell $::env(VCO_BAND_DELAY_CELL)
}
foreach {instance x y cell} [list \
    X0 0 0 $band_delay_cell \
    X1 70 0 $band_delay_cell \
    X2 140 0 $band_delay_cell \
    XBUF 210 0 $band_delay_cell \
    XSTART 0 45 cml_vco_startup_assist] {
    getcell $cell child 0 0 parent $x $y
    identify $instance
}
select top cell
load cml_vco_band_hier
units microns

# Three-stage odd ring and isolated buffer.  Every differential route uses the
# same layer and width; track pairs remain adjacent and independently spaced.
band_pair 0 70 -30.0 -32.2
band_pair 70 140 -34.4 -36.6
band_pair 140 0 -38.8 -41.0
band_pair 140 210 -43.2 -45.4

# Startup drains escape outward before rising, avoiding every internal child
# route.  They attach to the first stage's output node on matched M4 paths.
band_transition_34 -15 1.50
band_rect metal4 -31.0 1.12 -14.62 1.88
band_rect metal4 -31.0 1.12 -30.24 46.0
band_rect metal4 -31.0 45.62 -9.25 46.38
band_transition_34 15 1.50
band_rect metal4 14.62 1.12 31.0 1.88
band_rect metal4 30.24 1.12 31.0 46.0
band_rect metal4 9.25 45.62 31.0 46.38

# Common VDD on M5, VCTRL on M4, and a separate M3 VSS spine.
band_rect metal5 -1.0 24.70 211.0 27.00
band_port VDD 4 metal5 102.0 24.70 108.0 27.00
band_rect metal4 -24.0 -19.08 218.5 -18.32
band_port VCTRL 1 metal4 212.0 -19.08 218.5 -18.32
band_rect metal3 -27.0 -25.90 237.0 -25.10
foreach x {-26.5 43.5 113.5 183.5} {
    band_transition_35 $x -21.50
    # The child VSS label extends above its physical via landing.  Paint the
    # parent-owned M4/M5 bridge down to that landing; label extent alone does
    # not create conductor or hierarchical connectivity.
    foreach layer {metal4 metal5} {
        band_rect $layer [expr {$x-0.38}] -22.50 \
            [expr {$x+0.38}] -21.50
    }
    band_rect metal3 [expr {$x-0.38}] -25.90 \
        [expr {$x+0.38}] -21.50
}

# Startup VSS descends through the unused center gap of X0 to the M3 spine.
band_rect metal3 -0.38 -25.90 0.38 43.60
band_port VSS 5 metal3 -27.0 -25.90 -20.0 -25.10

# Startup controls and buffered clock are direct overlaps with child ports.
band_port KICKP 2 metal4 -4.45 38.50 -3.55 39.80
band_port KICKN 3 metal4 3.55 38.50 4.45 39.80
band_port CLK_P 6 metal3 194.0 1.05 197.5 1.95
band_port CLK_N 7 metal3 222.5 1.05 226.2 1.95

save cml_vco_band
gds write /work/cml_vco_band.gds
quit -noprompt
