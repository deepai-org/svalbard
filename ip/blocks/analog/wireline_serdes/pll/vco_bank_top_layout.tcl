# SPDX-License-Identifier: Apache-2.0
# Routed selected two-VCO bank: two bias DACs, two split-control VCOs, selector.

proc top_rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}
proc top_via {layer x y} {
    top_rect $layer [expr {$x-0.18}] [expr {$y-0.18}] \
        [expr {$x+0.18}] [expr {$y+0.18}]
}
proc top_transition_35 {x y} {
    foreach layer {metal3 metal4 metal5} {
        top_rect $layer [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
    }
    top_via via3 $x $y
    top_via via4 $x $y
}
proc top_transition_45 {x y} {
    foreach layer {metal4 metal5} {
        top_rect $layer [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
    }
    top_via via4 $x $y
}
set top_port_number 1
proc top_port {name layer x1 y1 x2 y2} {
    global top_port_number
    top_rect $layer $x1 $y1 $x2 $y2
    box values $x1 $y1 $x2 $y2
    label $name FreeSans 0.5 0 0 0 c $layer
    port make $top_port_number
    incr top_port_number
}

proc expose_dac_ports {prefix ox oy} {
    foreach {ch bit cx dir} {
        A 4 -76 -1 A 3 -61 -1 A 2 -46 -1 A 1 -31 -1 A 0 -16 -1
        B 4  76  1 B 3  61  1 B 2  46  1 B 1  31  1 B 0  16  1
    } {
        set high_x [expr {$ox+$cx+$dir*1.2}]
        set low_x [expr {$ox+$cx-$dir*1.2}]
        top_port ${prefix}_${ch}${bit} metal5 \
            [expr {$high_x-0.45}] [expr {$oy-31.2}] \
            [expr {$high_x+0.45}] [expr {$oy-28.8}]
        top_port ${prefix}_${ch}${bit}B metal4 \
            [expr {$low_x-0.45}] [expr {$oy-35.2}] \
            [expr {$low_x+0.45}] [expr {$oy-32.8}]
    }
}

proc route_bias {source_x source_y track_y target_x target_y} {
    top_rect metal5 [expr {$source_x-0.38}] \
        [expr {min($source_y,$track_y)-0.38}] [expr {$source_x+0.38}] \
        [expr {max($source_y,$track_y)+0.38}]
    top_transition_45 $source_x $track_y
    top_rect metal4 [expr {min($source_x,$target_x)-0.38}] \
        [expr {$track_y-0.38}] [expr {max($source_x,$target_x)+0.38}] \
        [expr {$track_y+0.38}]
    top_transition_45 $target_x $track_y
    top_rect metal5 [expr {$target_x-0.38}] \
        [expr {min($track_y,$target_y)-0.38}] [expr {$target_x+0.38}] \
        [expr {max($track_y,$target_y)+0.38}]
}

proc clock_escape {source_x source_y escape_x} {
    top_rect metal3 [expr {min($source_x,$escape_x)-0.38}] \
        [expr {$source_y-0.38}] [expr {max($source_x,$escape_x)+0.38}] \
        [expr {$source_y+0.38}]
    top_transition_35 $escape_x $source_y
}
proc clock_vertical {x y1 y2} {
    top_rect metal5 [expr {$x-0.38}] [expr {min($y1,$y2)-0.38}] \
        [expr {$x+0.38}] [expr {max($y1,$y2)+0.38}]
}
proc clock_horizontal {x1 x2 y} {
    top_rect metal4 [expr {min($x1,$x2)-0.38}] [expr {$y-0.38}] \
        [expr {max($x1,$x2)+0.38}] [expr {$y+0.38}]
}

crashbackups stop
load vco_bank_top_hier
units microns

foreach {instance x y cell} {
    XFDAC -140 -210 phase_control_dac
    XGDAC  140 -210 phase_control_dac
    XFAST -140    0 cml_vco_band_hr_split_fast
    XGAIN  140    0 cml_vco_band_hr_split_gain
    XSEL     0  270 phase_interpolator
} {
    getcell $cell child 0 0 parent $x $y
    identify $instance
}
select top cell
load vco_bank_top_hier
units microns

# Each DAC output reaches only its local VCO on a quiet, two-layer route.
route_bias -216 -147 -90 -98 42.8
route_bias  -64 -147 -80 -103 47.3
route_bias   64 -147 -90 182 46.3
route_bias  216 -147 -80 177 48.3

# Common references join identical DAC rails across the central quiet gap.
top_rect metal3 -58 -212.63 58 -211.87
top_port VREFH metal3 -5 -212.63 5 -211.87
top_rect metal3 -58 -228.63 58 -227.87
top_port VREFL metal3 -5 -228.63 5 -227.87

# VDD uses M5 perimeter spines; transitions occur only at child VDD ports.
foreach {x y} {-182 91 98 91} {
    top_transition_45 $x $y
    top_rect metal5 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] 315.38
}
top_rect metal5 -182.38 314.62 98.38 315.38
top_rect metal5 -4.38 294.0 -3.62 315.38
top_port VDD metal5 -47 314.55 -37 315.45

# VSS leaves every child at its existing ground port and joins outside macros.
top_rect metal3 -93.38 37.62 -45 38.38
top_transition_35 -45 38
top_rect metal3 187 37.62 235.38 38.38
top_transition_35 235 38
foreach x {-45 235} {
    top_rect metal5 [expr {$x-0.38}] -260.38 \
        [expr {$x+0.38}] 300.38
}
top_rect metal5 -55.4 -245.88 -44.62 -245.12
top_rect metal5 224.6 -245.88 235.38 -245.12
top_rect metal5 -45.38 269.62 -35.05 270.38
top_rect metal5 -45.38 -260.38 235.38 -259.62
top_port VSS metal5 90 -260.45 100 -259.55

# Clock routes escape each VCO on M3, rise outside the macro on M5, and use
# separate M4 tracks. Inner legs receive deliberate detours to equalize the
# pair lengths to first order before PEX.
clock_escape -154.35 193.5 -190
clock_vertical -190 193.5 224
top_transition_45 -190 224
clock_horizontal -190 -27 224
top_transition_45 -27 224
clock_vertical -27 224 243.6

clock_escape -125.65 193.5 -85
clock_vertical -85 193.5 226
top_transition_45 -85 226
clock_horizontal -85 35.5 226
top_transition_45 35.5 226
clock_vertical 35.5 226 228
top_transition_45 35.5 228
clock_horizontal 35.5 -3 228
top_transition_45 -3 228
clock_vertical -3 228 243.6

clock_escape 125.65 193.5 90
clock_vertical 90 193.5 230
top_transition_45 90 230
clock_horizontal 90 -70 230
top_transition_45 -70 230
clock_vertical -70 230 232
top_transition_45 -70 232
clock_horizontal -70 -19 232
top_transition_45 -19 232
clock_vertical -19 232 243.6

clock_escape 154.35 193.5 195
clock_vertical 195 193.5 234
top_transition_45 195 234
clock_horizontal 195 -11 234
top_transition_45 -11 234
clock_vertical -11 234 243.6

# Expose the two DAC code buses in schematic order.
expose_dac_ports F -140 -210
expose_dac_ports G 140 -210

# Startup, selector controls, and final differential clock remain explicit
# controller/top-level ports. Bias code zero is the independent VCO off state.
top_port FAST_KICKP metal4 -144.45 -60 -143.55 -50.2
top_port FAST_KICKN metal4 -136.45 -60 -135.55 -50.2
top_port GAIN_KICKP metal4 135.55 -60 136.45 -50.2
top_port GAIN_KICKN metal4 143.55 -60 144.45 -50.2
top_port SEL_A metal4 -42 254.42 -32.5 255.18
top_port SEL_B metal4 25.5 244.42 36 245.18
top_port SEL_BUF metal4 25.5 251.92 36 252.68
top_port CLK_P metal3 8.85 283.5 9.95 300
top_port CLK_N metal3 20.05 283.5 21.15 300

save vco_bank_top
gds write /work/vco_bank_top.gds
quit -noprompt
