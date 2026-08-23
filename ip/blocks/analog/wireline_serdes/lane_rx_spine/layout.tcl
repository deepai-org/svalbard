# SPDX-License-Identifier: Apache-2.0
# Parent-owned placement and matched routing for RX, restorer, and sampler.

proc spine_rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}
proc spine_via {layer x y} {
    spine_rect $layer [expr {$x-0.18}] [expr {$y-0.18}] \
        [expr {$x+0.18}] [expr {$y+0.18}]
}
proc spine_transition_34 {x y} {
    foreach layer {metal3 metal4} {
        spine_rect $layer [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
    }
    spine_via via3 $x $y
}
proc spine_transition_45 {x y} {
    foreach layer {metal4 metal5} {
        spine_rect $layer [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
    }
    spine_via via4 $x $y
}
proc spine_transition_35_array {x y} {
    foreach dx {-0.35 0.35} {
        foreach dy {-0.35 0.35} {
            spine_transition_34 [expr {$x+$dx}] [expr {$y+$dy}]
            spine_transition_45 [expr {$x+$dx}] [expr {$y+$dy}]
        }
    }
}
set spine_port_number 1
proc spine_port {name layer x1 y1 x2 y2} {
    global spine_port_number
    spine_rect $layer $x1 $y1 $x2 $y2
    box values $x1 $y1 $x2 $y2
    label $name FreeSans 0.5 0 0 0 c $layer
    port make $spine_port_number
    incr spine_port_number
}

crashbackups stop
load lane_rx_spine_hier
units microns
foreach {cell instance x y} {
    serdes_rx XRX 0 0
    cml_data_restorer_2p5_calibrated XREST 0 100
    cdr_sampler XSAMP 41 220
} {
    getcell $cell child 0 0 parent $x $y
    identify $instance
}
select top cell
load lane_rx_spine_hier
units microns

# RX output to restorer input.  Both branches have equal vertical and
# horizontal route span; the P branch uses a compact compensating jog.
spine_transition_34 9.4 26.0
spine_rect metal4 9.02 26.0 9.78 55.38
spine_rect metal4 -5.98 54.62 9.78 55.38
spine_rect metal4 -5.98 54.62 -5.22 70.38
spine_rect metal4 -5.98 69.62 -3.62 70.38
spine_rect metal4 -4.38 69.62 -3.62 75.38

spine_transition_34 20.6 26.0
spine_rect metal4 20.22 26.0 20.98 60.38
spine_rect metal4 3.62 59.62 20.98 60.38
spine_rect metal4 3.62 59.62 4.38 75.38
foreach x {-4 4} {
    spine_transition_45 $x 75.0
    spine_rect metal5 [expr {$x-0.38}] 75.0 [expr {$x+0.38}] 81.2
}

# Restorer outputs and sampler inputs reverse their left-to-right ordering.
# Cross them on different layers to prevent a hidden same-layer short.
spine_transition_34 -4.0 157.25
spine_rect metal4 -6.38 156.87 -3.62 157.63
spine_rect metal4 -6.38 156.87 -5.62 172.38
spine_transition_45 -6.0 172.0
spine_rect metal5 -6.38 172.0 -5.62 175.38
spine_rect metal5 -6.38 174.62 -1.62 175.38
spine_rect metal5 -2.38 174.62 -1.62 196.2

spine_transition_34 4.0 157.25
spine_rect metal4 3.62 156.87 6.38 157.63
spine_rect metal4 5.62 156.87 6.38 180.38
spine_rect metal4 -4.38 179.62 6.38 180.38
spine_rect metal4 -4.38 179.62 -3.62 196.2

# Sampler clocks and bias leave on separated tracks after clearing their pins.
# Do not broadside-overlap the high-impedance bias with either clock.
spine_rect metal5 1.62 195.37 95.0 196.13
spine_rect metal4 3.62 195.37 4.38 200.38
spine_rect metal4 3.62 199.62 95.0 200.38
spine_rect metal4 5.62 184.62 6.38 196.13
spine_rect metal4 5.62 184.62 95.0 185.38

# RX inputs and bias leave downward.  Bias changes to M4 before crossing VSS.
spine_rect metal4 -25.38 -45.0 -24.62 -20.8
spine_rect metal4 -17.38 -45.0 -16.62 -20.8
spine_transition_45 -3.0 -19.70
spine_rect metal4 -3.38 -45.0 -2.62 -19.32

# Thresholds and bandwidth escape left before the child's VDD stacks.
spine_transition_45 -23.0 33.5
spine_rect metal4 -52.0 33.12 -22.62 33.88
spine_transition_45 -19.0 33.5
spine_rect metal4 -19.38 30.12 -18.62 33.88
spine_rect metal4 -52.0 30.12 -18.62 30.88
spine_rect metal4 -52.0 22.92 -2.62 23.68

# Restorer bias remains independent and crosses its M5 inputs on M4.
spine_rect metal4 -52.0 80.22 0.45 80.98

# Wide side spines deliver supplies without sharing signal corridors.
spine_rect metal5 114.0 35.1 118.0 245.3
spine_rect metal5 -0.5 34.6 118.0 36.5
spine_rect metal5 8.9 167.6 118.0 169.5
spine_rect metal5 40.5 243.9 118.0 245.8
foreach y {35.55 168.55 244.85} { spine_transition_35_array 116.0 $y }

spine_rect metal5 -67.0 -1.5 -63.0 219.5
spine_rect metal5 -67.0 -1.5 -36.55 0.5
spine_rect metal5 -67.0 98.0 -13.05 100.0
spine_rect metal5 -67.0 218.0 -6.05 220.0
foreach y {-0.5 99.0 219.0} { spine_transition_35_array -65.0 $y }

# Sampler outputs escape sideways on M4 before the M3 load/VDD stacks.
foreach {name x escape_x} {
    EVEN_P 9 7 EVEN_N 25 23 ODD_P 57 59 ODD_N 73 75
} {
    spine_transition_34 $x 235.0
    spine_rect metal4 [expr {min($x,$escape_x)-0.38}] 234.62 \
        [expr {max($x,$escape_x)+0.38}] 235.38
    spine_rect metal4 [expr {$escape_x-0.38}] 234.62 \
        [expr {$escape_x+0.38}] 276.0
}

spine_port RXP metal4 -25.45 -46.0 -24.55 -43.5
spine_port RXN metal4 -17.45 -46.0 -16.55 -43.5
spine_port VTHP metal4 -53.0 33.05 -50.5 33.95
spine_port VTHN metal4 -53.0 30.05 -50.5 30.95
spine_port RX_BIAS metal4 -3.45 -46.0 -2.55 -43.5
spine_port RX_BW_EN_N metal4 -53.0 22.85 -50.5 23.75
spine_port REST_BIAS metal4 -53.0 80.15 -50.5 81.05
spine_port SAMP_CLK_P metal5 93.0 195.30 96.0 196.20
spine_port SAMP_CLK_N metal4 93.0 199.55 96.0 200.45
spine_port SAMP_BIAS metal4 93.0 184.55 96.0 185.45
spine_port VDD metal5 114.0 242.0 118.0 248.0
spine_port VSS metal5 -67.0 -4.0 -63.0 2.0
spine_port RX_RAWP metal4 9.02 42.0 9.78 45.0
spine_port RX_RAWN metal4 20.22 42.0 20.98 45.0
spine_port RX_RESTP metal5 -2.38 187.0 -1.62 190.0
spine_port RX_RESTN metal4 -4.38 187.0 -3.62 190.0
spine_port EVEN_P metal4 6.55 274.0 7.45 277.0
spine_port EVEN_N metal4 22.55 274.0 23.45 277.0
spine_port ODD_P metal4 58.55 274.0 59.45 277.0
spine_port ODD_N metal4 74.55 274.0 75.45 277.0

save /work/lane_rx_spine
gds write /work/lane_rx_spine.gds
quit -noprompt
