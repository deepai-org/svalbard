# SPDX-License-Identifier: Apache-2.0
# Parent-owned phase-interpolator-to-sampler clock routing.

proc pic_rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}
proc pic_via {layer x y} {
    pic_rect $layer [expr {$x-0.18}] [expr {$y-0.18}] \
        [expr {$x+0.18}] [expr {$y+0.18}]
}
proc pic_transition_34 {x y} {
    pic_rect metal3 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    pic_rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    pic_via via3 $x $y
}
proc pic_transition_35 {x y} {
    foreach layer {metal3 metal4 metal5} {
        pic_rect $layer [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
    }
    pic_via via3 $x $y
    pic_via via4 $x $y
}
proc pic_transition_45 {x y} {
    pic_rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    pic_rect metal5 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    pic_via via4 $x $y
}
set pic_port_number 1
proc pic_port {name layer x1 y1 x2 y2} {
    global pic_port_number
    pic_rect $layer $x1 $y1 $x2 $y2
    box values $x1 $y1 $x2 $y2
    label $name FreeSans 0.5 0 0 0 c $layer
    port make $pic_port_number
    incr pic_port_number
}

crashbackups stop
load lane_rx_pi_capture_hier
units microns
getcell lane_rx_capture child 0 0 parent 0 0
identify XRX
# A two-stage limiter isolates the interpolator from the sampler's four large
# clock-steering gates.  Both cells occupy otherwise unused sampler-side area.
getcell cml_clock_restorer_cascade child 0 0 parent 330 150
identify XCLKREST
getcell phase_interpolator child 0 0 parent 390 160
identify XPI
select top cell
load lane_rx_pi_capture_hier
units microns

# The PI outputs escape around both children on different layers.  P steps up
# before passing the N pin, and its M4 lower run stays above the M4 VSS return.
# N passes below the M5 supply drops.  The two paths therefore cross only on
# different layers and never share a transition enclosure.
pic_transition_34 399.4 174.25
pic_rect metal4 399.02 173.87 400.0 178.38
pic_rect metal4 399.02 177.62 430.38 178.38
pic_rect metal4 430.0 105.62 430.76 178.38
pic_rect metal4 325.62 105.62 430.76 106.38
pic_rect metal4 325.62 105.62 326.38 131.2
pic_transition_45 326.0 130.6

pic_transition_35 410.6 174.25
pic_rect metal5 410.22 173.87 434.38 174.63
pic_rect metal5 434.0 93.62 434.76 174.63
pic_rect metal5 333.62 93.62 434.76 94.38
pic_rect metal5 333.62 93.62 334.38 131.2

# Limiter P crosses the sampler's M5 VDD spine on M4.  N stays on its native
# M3 until the sampler endpoint.  The orthogonal layer assignment prevents
# the two heavily loaded clocks from sharing a parent-route crossing.
pic_rect metal3 325.55 207.25 326.45 211.0
pic_rect metal3 99.0 209.0 326.45 211.0
pic_rect metal3 99.0 195.75 101.0 211.0
pic_rect metal3 94.5 194.75 101.0 196.75
pic_transition_35 94.5 195.75

pic_rect metal3 333.55 207.25 334.45 215.0
pic_rect metal3 84.0 213.0 334.45 215.0
pic_rect metal3 84.0 199.0 86.0 215.0
pic_rect metal3 84.0 199.0 94.5 201.0
pic_transition_34 94.5 200.0
pic_rect metal4 93.0 199.55 96.0 200.45

# Each VDD joins an existing parent rail on M5.  The two guarded VSS ports
# leave along their child boundaries, then share a quiet M4 return to the
# right outer rail below all clock and phase routes.
pic_rect metal5 385.0 184.0 387.0 230.8
pic_rect metal5 285.0 230.0 387.0 230.8
pic_rect metal5 338.9 218.1 339.8 230.8
pic_rect metal5 316.05 99.62 316.95 150.0
pic_transition_45 316.5 100.0
pic_rect metal5 354.05 99.62 354.95 160.0
pic_transition_45 354.5 100.0
pic_rect metal4 275.0 99.62 354.88 100.38

# Existing lane ports, excluding the now-internal sampler clock pair.
pic_port RXP metal3 -41.4 -56.0 -40.6 -54.0
pic_port RXN metal3 -1.4 -56.0 -0.6 -54.0
set term_y {-117 -108 -99 -90 -81 -72 -63}
for {set index 0} {$index < 7} {incr index} {
    set y [lindex $term_y $index]
    pic_port TERM_EN${index}_N metal4 -59.0 [expr {$y-0.40}] \
        -58.0 [expr {$y+0.40}]
}
pic_port VTHP metal4 -53.0 33.05 -50.5 33.95
pic_port VTHN metal4 -53.0 30.05 -50.5 30.95
pic_port RX_BIAS metal4 -3.45 -46.0 -2.55 -43.5
pic_port RX_BW_EN_N metal4 -53.0 22.85 -50.5 23.75
pic_port REST_BIAS metal4 -53.0 80.15 -50.5 81.05
pic_port SAMP_BIAS metal4 93.0 184.55 96.0 185.45
pic_port E_SENSE_CLK metal5 11.55 339.35 12.45 340.25
pic_port E_REGEN_CLK metal5 -164.45 389.55 -163.55 390.45
pic_port E_REGEN_CLKB metal5 -166.45 390.95 -165.55 391.85
pic_port E_CAPTURE_CLK metal5 -148.25 469.55 -147.35 470.45
pic_port E_CAPTURE_CLKB metal5 -167.75 507.55 -166.85 508.45
pic_port E_SENSE_BOOST metal5 9.55 340.75 10.45 341.65
pic_port O_SENSE_CLK metal5 69.55 339.35 70.45 340.25
pic_port O_REGEN_CLK metal5 245.55 389.55 246.45 390.45
pic_port O_REGEN_CLKB metal5 247.55 390.95 248.45 391.85
pic_port O_CAPTURE_CLK metal5 232.35 474.55 233.25 475.45
pic_port O_CAPTURE_CLKB metal5 251.55 515.95 252.45 516.85
pic_port O_SENSE_BOOST metal5 71.55 340.75 72.45 341.65
pic_port VDD metal5 -202.0 -147.0 -198.0 -143.0
pic_port VSS metal4 -192.0 -137.0 -188.0 -133.0

# PI inputs and controls land on their native child layers.  The routed output
# pair remains observable for phase/swing measurement at the sampler boundary.
pic_port PHASE_A_P metal5 362.55 133.0 363.45 134.2
pic_port PHASE_A_N metal5 386.55 133.0 387.45 134.2
pic_port PHASE_B_P metal5 370.55 133.0 371.45 134.2
pic_port PHASE_B_N metal5 378.55 133.0 379.45 134.2
pic_port PI_CTRL_A metal4 356.0 144.42 357.5 145.18
pic_port PI_CTRL_B metal4 415.5 134.42 417.0 135.18
pic_port PI_BUF_BIAS metal4 415.5 141.92 417.0 142.68
pic_port CLK_REST_BIAS metal4 329.55 130.0 330.45 131.2
pic_port PI_RAW_P metal5 325.62 129.8 326.38 131.2
pic_port PI_RAW_N metal5 333.62 129.8 334.38 131.2
pic_port PI_CLK_P metal5 93.0 195.30 96.0 196.20
pic_port PI_CLK_N metal4 93.0 199.55 96.0 200.45

foreach {name layer x1 y1 x2 y2} {
    RX_RAWP metal4 9.02 42.0 9.78 45.0
    RX_RAWN metal4 20.22 42.0 20.98 45.0
    RX_RESTP metal5 -2.38 187.0 -1.62 190.0
    RX_RESTN metal4 -4.38 187.0 -3.62 190.0
    SAMP_E_P metal5 6.55 281.0 7.45 284.0
    SAMP_E_N metal5 22.55 281.0 23.45 284.0
    SAMP_O_P metal5 58.55 281.0 59.45 284.0
    SAMP_O_N metal5 74.55 281.0 75.45 284.0
    FE_E_P metal5 -166.45 383.75 -165.55 384.65
    FE_E_N metal5 11.55 382.35 12.45 383.25
    FE_O_P metal5 69.55 382.35 70.45 383.25
    FE_O_N metal5 247.55 383.75 248.45 384.65
    EVEN_Q metal5 -46.45 497.55 -45.55 498.45
    EVEN_QB metal5 -44.45 498.95 -43.55 499.85
    ODD_Q metal5 125.55 500.35 126.45 501.25
    ODD_QB metal5 127.55 501.75 128.45 502.65
} {
    pic_port $name $layer $x1 $y1 $x2 $y2
}

save /work/lane_rx_pi_capture
gds write /work/lane_rx_pi_capture.gds
quit -noprompt
