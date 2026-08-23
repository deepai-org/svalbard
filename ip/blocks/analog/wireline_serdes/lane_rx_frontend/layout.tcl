# SPDX-License-Identifier: Apache-2.0
# Parent-owned termination, CML receive spine, and dual converter routing.

proc front_rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}
proc front_via {layer x y} {
    front_rect $layer [expr {$x-0.18}] [expr {$y-0.18}] \
        [expr {$x+0.18}] [expr {$y+0.18}]
}
proc front_transition_45 {x y} {
    front_rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    front_rect metal5 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    front_via via4 $x $y
}
proc front_transition_35 {x y} {
    foreach layer {metal3 metal4 metal5} {
        front_rect $layer [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
    }
    front_via via3 $x $y
    front_via via4 $x $y
}
proc front_transition_34 {x y} {
    front_rect metal3 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    front_rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    front_via via3 $x $y
}
set front_port_number 1
proc front_port {name layer x1 y1 x2 y2} {
    global front_port_number
    front_rect $layer $x1 $y1 $x2 $y2
    box values $x1 $y1 $x2 $y2
    label $name FreeSans 0.5 0 0 0 c $layer
    port make $front_port_number
    incr front_port_number
}

crashbackups stop
load lane_rx_frontend_hier
units microns
getcell serdes_termination child 0 0 parent -26 -99
identify XTERM
rotate 270
getcell lane_rx_spine child 0 0 parent 0 0
identify XSPINE
getcell cml_to_cmos child 0 0 parent -77 352
identify XFE_E
sideways
getcell cml_to_cmos child 0 0 parent 159 352
identify XFE_O
select top cell
load lane_rx_frontend_hier
units microns

# The rotated termination presents long metal3 input buses at x=-41/-1.  Keep
# each net on metal3 until it has escaped above the metal4/metal5 control bank,
# then hand it directly to the spine's metal4 input.  The two paths have equal
# four-micron vertical escapes and equal sixteen-micron horizontal reaches.
front_rect metal3 -41.38 -53.38 -40.62 -48.62
front_rect metal3 -41.38 -49.38 -24.62 -48.62
front_transition_34 -25 -49
front_rect metal4 -25.38 -49.0 -24.62 -43.5

front_rect metal3 -1.38 -53.38 -0.62 -48.62
front_rect metal3 -17.38 -49.38 -0.62 -48.62
front_transition_34 -17 -49
front_rect metal4 -17.38 -49.0 -16.62 -43.5

# Sampler-to-converter routes stay matched within each interleave. The mirrored
# EVEN converter swaps both sides so its physical routes do not cross.
foreach {x0 y0 x1 y1} {
    7 275.5 14 338.4
    23 275.5 16 337.0
    59 275.5 66 337.0
    75 275.5 68 338.4
} {
    front_transition_45 $x0 $y0
    front_rect metal5 [expr {$x0-0.38}] $y0 \
        [expr {$x0+0.38}] [expr {$y1+0.38}]
    front_rect metal5 [expr {min($x0,$x1)-0.38}] [expr {$y1-0.38}] \
        [expr {max($x0,$x1)+0.38}] [expr {$y1+0.38}]
}

# Symmetric outer supply rails avoid threading power through either converter.
front_rect metal5 -202 -147 -198 440
front_rect metal5 283 -147 287 440
front_rect metal5 -202 -147 287 -143
front_rect metal4 -192 -137 -188 324
front_rect metal4 273 -137 277 324
front_rect metal4 -192 -137 277 -133

# VDD branches: converters see nearly equal reach to opposite outer rails.
front_rect metal5 -200.0 435.0 10.0 439.0
front_rect metal5 72.0 435.0 285.0 439.0
front_rect metal5 114.0 243.0 285.0 247.0
front_rect metal5 -200.0 -132.0 -57.12 -128.0
front_rect metal5 -57.88 -130.0 -57.12 -89.5

# VSS uses M4 so its crossings with M5 signal and VDD routes are intentional.
front_transition_45 -21 -121
front_rect metal4 -190.0 -123.0 -21.0 -119.0
front_rect metal4 -190.0 -2.0 -65.0 2.0
front_rect metal4 -190.0 320.0 -162.0 324.0
front_rect metal4 244.0 320.0 275.0 324.0

# External differential and termination controls.
front_port RXP metal3 -41.4 -56.0 -40.6 -54.0
front_port RXN metal3 -1.4 -56.0 -0.6 -54.0
set term_y {-117 -108 -99 -90 -81 -72 -63}
for {set index 0} {$index < 7} {incr index} {
    set y [lindex $term_y $index]
    front_port TERM_EN${index}_N metal4 -59.0 [expr {$y-0.40}] \
        -58.0 [expr {$y+0.40}]
}

# Spine controls and diagnostic nodes remain observable at natural child pins.
front_port VTHP metal4 -53.0 33.05 -50.5 33.95
front_port VTHN metal4 -53.0 30.05 -50.5 30.95
front_port RX_BIAS metal4 -3.45 -46.0 -2.55 -43.5
front_port RX_BW_EN_N metal4 -53.0 22.85 -50.5 23.75
front_port REST_BIAS metal4 -53.0 80.15 -50.5 81.05
front_port SAMP_CLK_P metal5 93.0 195.30 96.0 196.20
front_port SAMP_CLK_N metal4 93.0 199.55 96.0 200.45
front_port SAMP_BIAS metal4 93.0 184.55 96.0 185.45

# Converter controls. Their mirrored placement keeps the two sets on the outer
# edges and leaves the central channel for differential data only.
front_port E_SENSE_CLK metal5 11.55 339.35 12.45 340.25
front_port E_REGEN_CLK metal5 -164.45 389.55 -163.55 390.45
front_port E_REGEN_CLKB metal5 -166.45 390.95 -165.55 391.85
front_port E_CAPTURE_CLK metal5 -168.45 385.55 -167.55 386.45
front_port E_CAPTURE_CLKB metal5 -170.45 386.95 -169.55 387.85
front_port E_SENSE_BOOST metal5 9.55 340.75 10.45 341.65
front_port O_SENSE_CLK metal5 69.55 339.35 70.45 340.25
front_port O_REGEN_CLK metal5 245.55 389.55 246.45 390.45
front_port O_REGEN_CLKB metal5 247.55 390.95 248.45 391.85
front_port O_CAPTURE_CLK metal5 249.55 385.55 250.45 386.45
front_port O_CAPTURE_CLKB metal5 251.55 386.95 252.45 387.85
front_port O_SENSE_BOOST metal5 71.55 340.75 72.45 341.65

front_port VDD metal5 -202.0 -147.0 -198.0 -143.0
front_port VSS metal4 -192.0 -137.0 -188.0 -133.0
front_port RX_RAWP metal4 9.02 42.0 9.78 45.0
front_port RX_RAWN metal4 20.22 42.0 20.98 45.0
front_port RX_RESTP metal5 -2.38 187.0 -1.62 190.0
front_port RX_RESTN metal4 -4.38 187.0 -3.62 190.0
front_port SAMP_E_P metal5 6.55 281.0 7.45 284.0
front_port SAMP_E_N metal5 22.55 281.0 23.45 284.0
front_port SAMP_O_P metal5 58.55 281.0 59.45 284.0
front_port SAMP_O_N metal5 74.55 281.0 75.45 284.0
front_port FE_E_P metal5 -166.45 383.75 -165.55 384.65
front_port FE_E_N metal5 11.55 382.35 12.45 383.25
front_port FE_O_P metal5 69.55 382.35 70.45 383.25
front_port FE_O_N metal5 247.55 383.75 248.45 384.65

save /work/lane_rx_frontend
gds write /work/lane_rx_frontend.gds
quit -noprompt
