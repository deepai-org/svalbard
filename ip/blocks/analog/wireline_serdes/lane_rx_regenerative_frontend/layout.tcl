# SPDX-License-Identifier: Apache-2.0
# Compact termination/RX/dual-StrongARM parent for direct regenerative sampling.

proc regen_rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}
proc regen_via {layer x y} {
    regen_rect $layer [expr {$x-0.18}] [expr {$y-0.18}] \
        [expr {$x+0.18}] [expr {$y+0.18}]
}
proc regen_transition_34 {x y} {
    regen_rect metal3 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    regen_rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    regen_via via3 $x $y
}
proc regen_transition_45 {x y} {
    regen_rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    regen_rect metal5 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    regen_via via4 $x $y
}
set regen_port_number 1
proc regen_port {name layer x1 y1 x2 y2} {
    global regen_port_number
    regen_rect $layer $x1 $y1 $x2 $y2
    box values $x1 $y1 $x2 $y2
    label $name FreeSans 0.5 0 0 0 c $layer
    port make $regen_port_number
    incr regen_port_number
}

crashbackups stop
load lane_rx_regenerative_frontend_hier
units microns
getcell serdes_termination child 0 0 parent -26 -99
identify XTERM
rotate 270
getcell serdes_rx child 0 0 parent 0 0
identify XRX
# Face both converter input edges toward the receiver. Their full-width VSS
# meshes sit at y=80 um; parent data stays on M3/M4 until above that mesh.
getcell cml_to_cmos child 0 0 parent -102 110
identify XFE_E
sideways
getcell cml_to_cmos child 0 0 parent 134 110
identify XFE_O
select top cell
load lane_rx_regenerative_frontend_hier
units microns

# Termination-to-RX routes retain the proven equal 16-um horizontal reach.
regen_rect metal3 -41.38 -53.38 -40.62 -48.62
regen_rect metal3 -41.38 -49.38 -24.62 -48.62
regen_transition_34 -25 -49
regen_rect metal4 -25.38 -49.0 -24.62 -20.8
regen_rect metal3 -1.38 -53.38 -0.62 -48.62
regen_rect metal3 -17.38 -49.38 -0.62 -48.62
regen_transition_34 -17 -49
regen_rect metal4 -17.38 -49.0 -16.62 -20.8

# RX P fans out on M4. RX N fans out on M3, then rises on M4 after crossing
# the P trunk. Both pairs enter their child M5 pins only above the y=80 VSS
# meshes. Small outward jogs equalize the two routes within each interleave.
regen_transition_34 9.4 26.0
regen_rect metal4 9.02 26.0 9.78 54.38
regen_rect metal4 -16.38 53.62 9.78 54.38
regen_rect metal4 -16.38 53.62 -15.62 58.38
regen_rect metal4 -16.38 57.62 -10.62 58.38
regen_rect metal4 -11.38 57.62 -10.62 89.38
regen_transition_45 -11.0 89.0
regen_rect metal5 -11.38 89.0 -10.62 96.85
regen_rect metal4 9.02 53.62 41.38 54.38
regen_rect metal4 40.62 53.62 41.38 89.38
regen_transition_45 41.0 89.0
regen_rect metal5 40.62 89.0 41.38 95.45

regen_rect metal3 20.22 26.0 20.98 64.38
regen_rect metal3 -9.38 63.62 20.98 64.38
regen_transition_34 -9.0 64.0
regen_rect metal4 -9.38 64.0 -8.62 90.78
regen_transition_45 -9.0 90.4
regen_rect metal5 -9.38 90.4 -8.62 95.45
regen_rect metal3 20.22 63.62 47.38 64.38
regen_rect metal3 46.62 59.62 47.38 64.38
regen_rect metal3 42.62 59.62 47.38 60.38
regen_transition_34 43.0 60.0
regen_rect metal4 42.62 60.0 43.38 90.78
regen_transition_45 43.0 90.4
regen_rect metal5 42.62 90.4 43.38 96.85

# Wide outer supplies keep clock and data corridors free. VDD remains on M5;
# VSS enters each converter on M4 after a local M4/M5 transition.
regen_rect metal5 -227 -147 -223 201
regen_rect metal5 255 -147 259 201
regen_rect metal5 -227 -147 259 -143
regen_rect metal5 -227 197 259 201
regen_rect metal5 0.0 33.5 259 37.5
regen_rect metal5 -227 -132 -57.12 -128
regen_rect metal5 -57.88 -130 -57.12 -89.5

regen_rect metal4 -217 -137 -213 84
regen_rect metal4 245 -137 249 84
regen_rect metal4 -217 -137 249 -133
regen_transition_45 -21 -121
regen_rect metal4 -215 -123 -21 -119
regen_transition_45 -37 -0.5
regen_rect metal4 -215 -2.5 -37 1.5
regen_transition_45 -187 80
regen_rect metal4 -215 78 -187 82
regen_transition_45 219 80
regen_rect metal4 219 78 247 82

# External differential inputs and termination controls.
regen_port RXP metal3 -41.4 -56.0 -40.6 -54.0
regen_port RXN metal3 -1.4 -56.0 -0.6 -54.0
set term_y {-117 -108 -99 -90 -81 -72 -63}
for {set index 0} {$index < 7} {incr index} {
    set y [lindex $term_y $index]
    regen_port TERM_EN${index}_N metal4 -59.0 [expr {$y-0.40}] \
        -58.0 [expr {$y+0.40}]
}
regen_port VTHP metal5 -23.5 33.0 -22.5 34.0
regen_port VTHN metal5 -19.5 33.0 -18.5 34.0
regen_transition_45 -3.0 -19.7
regen_rect metal4 -3.38 -45.0 -2.62 -19.32
regen_port RX_BIAS metal4 -3.45 -46.0 -2.55 -43.5
regen_port RX_BW_EN_N metal4 -4.0 22.92 -2.0 23.68

# Independent sense/boost ports are the physical phase-trim boundary.
foreach {name layer x y} {
    E_SENSE_CLK metal5 -13 97.8
    E_REGEN_CLK metal5 -189 148.0
    E_REGEN_CLKB metal5 -191 149.4
    E_CAPTURE_CLK metal5 -193 144.0
    E_CAPTURE_CLKB metal5 -195 145.4
    E_SENSE_BOOST metal5 -15 99.2
    O_SENSE_CLK metal5 45 97.8
    O_REGEN_CLK metal5 221 148.0
    O_REGEN_CLKB metal5 223 149.4
    O_CAPTURE_CLK metal5 225 144.0
    O_CAPTURE_CLKB metal5 227 145.4
    O_SENSE_BOOST metal5 47 99.2
} {
    regen_port $name $layer [expr {$x-0.45}] [expr {$y-0.45}] \
        [expr {$x+0.45}] [expr {$y+0.45}]
}

regen_port VDD metal5 -227 -147 -223 -143
regen_port VSS metal4 -217 -137 -213 -133
regen_port RX_RAWP metal4 9.02 42.0 9.78 45.0
regen_port RX_RAWN metal3 20.22 42.0 20.98 45.0
regen_port FE_E_P metal5 -191.45 141.75 -190.55 142.65
regen_port FE_E_N metal5 -13.45 140.35 -12.55 141.25
regen_port FE_O_P metal5 44.55 140.35 45.45 141.25
regen_port FE_O_N metal5 222.55 141.75 223.45 142.65

save /work/lane_rx_regenerative_frontend
gds write /work/lane_rx_regenerative_frontend.gds
quit -noprompt
