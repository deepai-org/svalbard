# SPDX-License-Identifier: Apache-2.0
# Parent-owned placement and routing for VCO bank, clock restorer, and divider.

proc path_rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}
proc path_via {layer x y} {
    path_rect $layer [expr {$x-0.18}] [expr {$y-0.18}] \
        [expr {$x+0.18}] [expr {$y+0.18}]
}
proc path_transition_34 {x y} {
    foreach layer {metal3 metal4} {
        path_rect $layer [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
    }
    path_via via3 $x $y
}
proc path_transition_35 {x y} {
    foreach layer {metal3 metal4 metal5} {
        path_rect $layer [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
    }
    path_via via3 $x $y
    path_via via4 $x $y
}
proc path_transition_45 {x y} {
    foreach layer {metal4 metal5} {
        path_rect $layer [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
    }
    path_via via4 $x $y
}
proc path_transition_35_array {x y} {
    foreach dx {-0.35 0.35} {
        foreach dy {-0.35 0.35} {
            path_transition_35 [expr {$x+$dx}] [expr {$y+$dy}]
        }
    }
}
set path_port_number 1
proc path_port {name layer x1 y1 x2 y2} {
    global path_port_number
    path_rect $layer $x1 $y1 $x2 $y2
    box values $x1 $y1 $x2 $y2
    label $name FreeSans 0.5 0 0 0 c $layer
    port make $path_port_number
    incr path_port_number
}
proc path_dac_ports {prefix ox oy} {
    foreach {ch bit cx dir} {
        A 4 -76 -1 A 3 -61 -1 A 2 -46 -1 A 1 -31 -1 A 0 -16 -1
        B 4  76  1 B 3  61  1 B 2  46  1 B 1  31  1 B 0  16  1
    } {
        set high_x [expr {$ox+$cx+$dir*1.2}]
        set low_x [expr {$ox+$cx-$dir*1.2}]
        path_port ${prefix}_${ch}${bit} metal5 \
            [expr {$high_x-0.45}] [expr {$oy-31.2}] \
            [expr {$high_x+0.45}] [expr {$oy-28.8}]
        path_port ${prefix}_${ch}${bit}B metal4 \
            [expr {$low_x-0.45}] [expr {$oy-35.2}] \
            [expr {$low_x+0.45}] [expr {$oy-32.8}]
    }
}

crashbackups stop
load pll_clock_path_hier
units microns
foreach {cell instance x y} {
    vco_bank_top XBANK 0 0
    cml_clock_restorer_cascade XREST 15 340
    cml_divider_by_2 XDIV 53.4 445
} {
    getcell $cell child 0 0 parent $x $y
    identify $instance
}
select top cell
load pll_clock_path_hier
units microns

# VCO-bank M3 clocks cross its M5 supply rail on M4, then enter the limiter
# only after rising to M5 in the narrow channel between the two children.
foreach {bank_x rest_x} {9.4 11.0 20.6 19.0} {
    path_transition_34 $bank_x 299.0
    path_rect metal4 [expr {$bank_x-0.38}] 299.0 \
        [expr {$bank_x+0.38}] 317.0
    path_rect metal4 [expr {min($bank_x,$rest_x)-0.38}] 316.62 \
        [expr {max($bank_x,$rest_x)+0.38}] 317.38
    path_transition_45 $rest_x 317.0
    path_rect metal5 [expr {$rest_x-0.38}] 317.0 \
        [expr {$rest_x+0.38}] 320.3
}

# Limiter outputs remain on matched M4 routes past its M5 VDD rail.  The P
# branch changes to the divider's M5 clock only in the open inter-cell gap.
foreach {rest_x escape_x div_x use_m5} {11.0 9.0 14.02 1 19.0 21.0 16.02 0} {
    path_transition_34 $rest_x 397.4
    path_rect metal4 [expr {min($rest_x,$escape_x)-0.38}] 397.02 \
        [expr {max($rest_x,$escape_x)+0.38}] 397.78
    path_rect metal4 [expr {$escape_x-0.38}] 397.02 \
        [expr {$escape_x+0.38}] 414.38
    path_rect metal4 [expr {min($escape_x,$div_x)-0.38}] 413.62 \
        [expr {max($escape_x,$div_x)+0.38}] 414.38
    if {$use_m5} {
        path_transition_45 $div_x 414.0
        path_rect metal5 [expr {$div_x-0.38}] 414.0 \
            [expr {$div_x+0.38}] 421.0
    } else {
        path_rect metal4 [expr {$div_x-0.38}] 414.0 \
            [expr {$div_x+0.38}] 421.0
    }
}

# VDD reaches the limiter on a quiet central M5 spine, then escapes right of
# the divider before returning to its top rail.  VSS crosses the VDD spine on
# M3 and subsequently stays outside the divider's left guard.
path_rect metal5 -47.0 312.4 26.5 315.45
path_rect metal5 21.5 312.4 26.5 414.5
path_rect metal5 21.5 409.5 112.5 414.5
path_rect metal5 107.5 409.5 112.5 472.5
path_rect metal5 52.0 467.5 112.5 472.5

path_rect metal5 88.0 -262.5 237.5 -257.5
path_rect metal5 232.5 -262.5 237.5 343.0
path_transition_35_array 235.0 341.0
path_rect metal3 0.0 340.5 235.0 341.5
path_transition_35_array 1.5 341.0
path_rect metal5 0.0 338.0 3.0 445.5
path_rect metal5 0.0 442.5 6.5 445.5

# Re-expose the complete VCO control interface in its canonical order.
path_port VREFH metal3 -5 -212.63 5 -211.87
path_port VREFL metal3 -5 -228.63 5 -227.87
path_port VDD metal5 -47 314.55 -37 315.45
path_port VSS metal5 90 -260.45 100 -259.55
path_dac_ports F -140 -210
path_dac_ports G 140 -210
path_port FAST_KICKP metal4 -144.45 -60 -143.55 -50.2
path_port FAST_KICKN metal4 -136.45 -60 -135.55 -50.2
path_port GAIN_KICKP metal4 135.55 -60 136.45 -50.2
path_port GAIN_KICKN metal4 143.55 -60 144.45 -50.2
path_port SEL_A metal4 -42 254.42 -32.5 255.18
path_port SEL_B metal4 25.5 244.42 36 245.18
path_port SEL_BUF metal4 25.5 251.92 36 252.68

path_port REST_BIAS metal4 14.55 320.0 15.45 321.2
path_port DIV_RESET metal5 53.02 420.0 53.78 421.5
path_port DIV_BIAS metal4 17.57 420.0 18.47 421.5
path_port DIV_P metal3 68.95 458.5 69.85 460.5
path_port DIV_N metal3 84.95 458.5 85.85 460.5

save /work/pll_clock_path
gds write /work/pll_clock_path.gds
quit -noprompt
