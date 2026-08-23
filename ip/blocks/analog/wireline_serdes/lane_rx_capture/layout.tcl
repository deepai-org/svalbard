# SPDX-License-Identifier: Apache-2.0
# Parent-owned converter-to-capture data, clock, and supply routing.

proc cap_rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}
proc cap_via {layer x y} {
    cap_rect $layer [expr {$x-0.18}] [expr {$y-0.18}] \
        [expr {$x+0.18}] [expr {$y+0.18}]
}
proc cap_transition_34 {x y} {
    cap_rect metal3 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    cap_rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    cap_via via3 $x $y
}
proc cap_transition_35 {x y} {
    foreach layer {metal3 metal4 metal5} {
        cap_rect $layer [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
    }
    cap_via via3 $x $y
    cap_via via4 $x $y
}
set cap_port_number 1
proc cap_port {name layer x1 y1 x2 y2} {
    global cap_port_number
    cap_rect $layer $x1 $y1 $x2 $y2
    box values $x1 $y1 $x2 $y2
    label $name FreeSans 0.5 0 0 0 c $layer
    port make $cap_port_number
    incr cap_port_number
}

crashbackups stop
load lane_rx_capture_hier
units microns
getcell lane_rx_frontend child 0 0 parent 0 0
identify XFRONT
# Center the capture array on the front end's x=41 symmetry axis.  A 35 um
# vertical channel separates its VSS guard from the front end's top VDD rail.
getcell deserializer_split_capture child 0 0 parent 41 475
identify XCAP
select top cell
load lane_rx_capture_hier
units microns

# Continue both parent rails around the capture cell.  VDD stays on M5 and
# lands on the capture's upper well rail; VSS stays on M4 and lands on its
# lower substrate rail, so neither supply blocks the signal escape channel.
cap_rect metal5 -202 440 -198 570
cap_rect metal5 283 440 287 570
cap_rect metal5 -202 558 287 562
cap_rect metal4 -192 320 -188 445
cap_rect metal4 273 320 277 445
cap_rect metal4 -192 443 277 447

# Each CMOS data route first escapes its converter on M5, then uses the same
# 128 um of M4 and four M3/M4 turns.  The layer drop is outside all converter
# geometry: child pin columns are intentionally reused at different y tracks,
# so extending one of those columns on M3 would short otherwise distinct nets.
# inner routes deliberately dogleg outward; otherwise their RC would be about
# forty microns shorter than the outer routes.  M3 verticals cross the M5 VDD
# rail without contact.  Endpoint y offsets are inherited from the capture's
# staggered pin tracks and remain below 4.2 um.
foreach route {
    {-166.0 384.2 -180.0 -116.0 448.5 449.9 -52.0 460.0}
    {  12.0 382.8   24.0  -77.0 451.3 452.7 -50.0 461.4}
    {  70.0 382.8   58.0  159.0 454.1 455.5 132.0 462.8}
    { 248.0 384.2  262.0  198.0 456.9 458.3 134.0 464.2}
} {
    lassign $route px py sx wx ylo yhi dx dy
    cap_rect metal5 [expr {min($px,$sx)-0.38}] [expr {$py-0.38}] \
        [expr {max($px,$sx)+0.38}] [expr {$py+0.38}]
    cap_transition_35 $sx $py
    cap_rect metal3 [expr {$sx-0.23}] $py [expr {$sx+0.23}] \
        [expr {$ylo+0.38}]
    cap_transition_34 $sx $ylo
    cap_rect metal4 [expr {min($sx,$wx)-0.38}] [expr {$ylo-0.38}] \
        [expr {max($sx,$wx)+0.38}] [expr {$ylo+0.38}]
    cap_transition_34 $wx $ylo
    cap_rect metal3 [expr {$wx-0.23}] [expr {$ylo-0.38}] \
        [expr {$wx+0.23}] [expr {$yhi+0.38}]
    cap_transition_34 $wx $yhi
    cap_rect metal4 [expr {min($wx,$dx)-0.38}] [expr {$yhi-0.38}] \
        [expr {max($wx,$dx)+0.38}] [expr {$yhi+0.38}]
    cap_transition_34 $dx $yhi
    cap_rect metal3 [expr {$dx-0.23}] [expr {$yhi-0.38}] \
        [expr {$dx+0.23}] $dy
}

# Capture clocks leave their converter pins vertically on M3, cross the front
# end VDD rail without contact, and then fan into the capture on M5.  The four
# clocks remain independent so extracted skew can be calibrated per interleave.
foreach route {
    {-168.0 386.0 470.0 -48.0 465.6}
    {-170.0 387.4 508.0 -47.0 505.0}
    { 250.0 386.0 475.0 129.0 472.6}
    { 252.0 387.4 521.0 130.0 518.6}
} {
    lassign $route sx sy ty dx dy
    cap_rect metal3 [expr {$sx-0.23}] $sy [expr {$sx+0.23}] \
        [expr {$ty+0.38}]
    cap_transition_35 $sx $ty
    cap_rect metal5 [expr {min($sx,$dx)-0.38}] [expr {$ty-0.38}] \
        [expr {max($sx,$dx)+0.38}] [expr {$ty+0.38}]
    cap_rect metal5 [expr {$dx-0.38}] [expr {min($ty,$dy)-0.38}] \
        [expr {$dx+0.38}] [expr {max($ty,$dy)+0.38}]
}
# The odd complement route's electrical midpoint falls on its long M3 rise;
# expose that point through a local M3-to-M5 landing.  The other three
# midpoints fall directly on their horizontal M5 trunks.
cap_transition_35 252.0 516.4

# Preserve every front-end control and stage probe at its natural landing.
cap_port RXP metal3 -41.4 -56.0 -40.6 -54.0
cap_port RXN metal3 -1.4 -56.0 -0.6 -54.0
set term_y {-117 -108 -99 -90 -81 -72 -63}
for {set index 0} {$index < 7} {incr index} {
    set y [lindex $term_y $index]
    cap_port TERM_EN${index}_N metal4 -59.0 [expr {$y-0.40}] \
        -58.0 [expr {$y+0.40}]
}
cap_port VTHP metal4 -53.0 33.05 -50.5 33.95
cap_port VTHN metal4 -53.0 30.05 -50.5 30.95
cap_port RX_BIAS metal4 -3.45 -46.0 -2.55 -43.5
cap_port RX_BW_EN_N metal4 -53.0 22.85 -50.5 23.75
cap_port REST_BIAS metal4 -53.0 80.15 -50.5 81.05
cap_port SAMP_CLK_P metal5 93.0 195.30 96.0 196.20
cap_port SAMP_CLK_N metal4 93.0 199.55 96.0 200.45
cap_port SAMP_BIAS metal4 93.0 184.55 96.0 185.45
cap_port E_SENSE_CLK metal5 11.55 339.35 12.45 340.25
cap_port E_REGEN_CLK metal5 -164.45 389.55 -163.55 390.45
cap_port E_REGEN_CLKB metal5 -166.45 390.95 -165.55 391.85
cap_port E_CAPTURE_CLK metal5 -148.25 469.55 -147.35 470.45
cap_port E_CAPTURE_CLKB metal5 -167.75 507.55 -166.85 508.45
cap_port E_SENSE_BOOST metal5 9.55 340.75 10.45 341.65
cap_port O_SENSE_CLK metal5 69.55 339.35 70.45 340.25
cap_port O_REGEN_CLK metal5 245.55 389.55 246.45 390.45
cap_port O_REGEN_CLKB metal5 247.55 390.95 248.45 391.85
cap_port O_CAPTURE_CLK metal5 232.35 474.55 233.25 475.45
cap_port O_CAPTURE_CLKB metal5 251.55 515.95 252.45 516.85
cap_port O_SENSE_BOOST metal5 71.55 340.75 72.45 341.65
cap_port VDD metal5 -202.0 -147.0 -198.0 -143.0
cap_port VSS metal4 -192.0 -137.0 -188.0 -133.0
cap_port RX_RAWP metal4 9.02 42.0 9.78 45.0
cap_port RX_RAWN metal4 20.22 42.0 20.98 45.0
cap_port RX_RESTP metal5 -2.38 187.0 -1.62 190.0
cap_port RX_RESTN metal4 -4.38 187.0 -3.62 190.0
cap_port SAMP_E_P metal5 6.55 281.0 7.45 284.0
cap_port SAMP_E_N metal5 22.55 281.0 23.45 284.0
cap_port SAMP_O_P metal5 58.55 281.0 59.45 284.0
cap_port SAMP_O_N metal5 74.55 281.0 75.45 284.0
cap_port FE_E_P metal5 -166.45 383.75 -165.55 384.65
cap_port FE_E_N metal5 11.55 382.35 12.45 383.25
cap_port FE_O_P metal5 69.55 382.35 70.45 383.25
cap_port FE_O_N metal5 247.55 383.75 248.45 384.65
cap_port EVEN_Q metal5 -46.45 497.55 -45.55 498.45
cap_port EVEN_QB metal5 -44.45 498.95 -43.55 499.85
cap_port ODD_Q metal5 125.55 500.35 126.45 501.25
cap_port ODD_QB metal5 127.55 501.75 128.45 502.65

save /work/lane_rx_capture
gds write /work/lane_rx_capture.gds
quit -noprompt
