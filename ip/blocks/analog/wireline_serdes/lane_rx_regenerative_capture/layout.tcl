# SPDX-License-Identifier: Apache-2.0
# Parent-owned StrongARM-to-static-capture routing.

proc regcap_rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}
proc regcap_via {layer x y} {
    regcap_rect $layer [expr {$x-0.18}] [expr {$y-0.18}] \
        [expr {$x+0.18}] [expr {$y+0.18}]
}
proc regcap_transition_34 {x y} {
    regcap_rect metal3 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    regcap_rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    regcap_via via3 $x $y
}
proc regcap_transition_35 {x y} {
    foreach layer {metal3 metal4 metal5} {
        regcap_rect $layer [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
    }
    regcap_via via3 $x $y
    regcap_via via4 $x $y
}
set regcap_port_number 1
proc regcap_port {name layer x1 y1 x2 y2} {
    global regcap_port_number
    regcap_rect $layer $x1 $y1 $x2 $y2
    box values $x1 $y1 $x2 $y2
    label $name FreeSans 0.5 0 0 0 c $layer
    port make $regcap_port_number
    incr regcap_port_number
}

crashbackups stop
load lane_rx_regenerative_capture_hier
units microns
getcell lane_rx_regenerative_frontend child 0 0 parent 0 0
identify XFRONT
getcell deserializer_split_capture child 0 0 parent 41 235
identify XCAP
select top cell
load lane_rx_regenerative_capture_hier
units microns

# Extend the front-end outer rails to the capture cell without entering any
# differential data corridor.
regcap_rect metal5 -227 197 -223 330
regcap_rect metal5 255 197 259 330
regcap_rect metal5 -227 318 259 322
regcap_rect metal4 -217 78 -213 207
regcap_rect metal4 245 78 249 207
regcap_rect metal4 -217 203 249 207

# Translate the previously closed four-route capture pattern downward and
# toward the new converter placement. Each pair remains matched within 2 um.
foreach route {
    {-191.0 142.2 -205.0 -141.0 208.5 209.9 -52.0 220.0}
    { -13.0 140.8   -2.0 -102.0 211.3 212.7 -50.0 221.4}
    {  45.0 140.8   33.0  134.0 214.1 215.5 132.0 222.8}
    { 223.0 142.2  237.0  173.0 216.9 218.3 134.0 224.2}
} {
    lassign $route px py sx wx ylo yhi dx dy
    regcap_rect metal5 [expr {min($px,$sx)-0.38}] [expr {$py-0.38}] \
        [expr {max($px,$sx)+0.38}] [expr {$py+0.38}]
    regcap_transition_35 $sx $py
    regcap_rect metal3 [expr {$sx-0.23}] $py [expr {$sx+0.23}] \
        [expr {$ylo+0.38}]
    regcap_transition_34 $sx $ylo
    regcap_rect metal4 [expr {min($sx,$wx)-0.38}] [expr {$ylo-0.38}] \
        [expr {max($sx,$wx)+0.38}] [expr {$ylo+0.38}]
    regcap_transition_34 $wx $ylo
    regcap_rect metal3 [expr {$wx-0.23}] [expr {$ylo-0.38}] \
        [expr {$wx+0.23}] [expr {$yhi+0.38}]
    regcap_transition_34 $wx $yhi
    regcap_rect metal4 [expr {min($wx,$dx)-0.38}] [expr {$yhi-0.38}] \
        [expr {max($wx,$dx)+0.38}] [expr {$yhi+0.38}]
    regcap_transition_34 $dx $yhi
    regcap_rect metal3 [expr {$dx-0.23}] [expr {$yhi-0.38}] \
        [expr {$dx+0.23}] $dy
}

# Independent capture clocks follow their converter-side columns before
# fanning into the static capture. The separate routes preserve trim freedom.
foreach route {
    {-193.0 144.0 230.0 -48.0 225.6}
    {-195.0 145.4 268.0 -47.0 265.0}
    { 225.0 144.0 235.0 129.0 232.6}
    { 227.0 145.4 281.0 130.0 278.6}
} {
    lassign $route sx sy ty dx dy
    regcap_rect metal3 [expr {$sx-0.23}] $sy [expr {$sx+0.23}] \
        [expr {$ty+0.38}]
    regcap_transition_35 $sx $ty
    regcap_rect metal5 [expr {min($sx,$dx)-0.38}] [expr {$ty-0.38}] \
        [expr {max($sx,$dx)+0.38}] [expr {$ty+0.38}]
    regcap_rect metal5 [expr {$dx-0.38}] [expr {min($ty,$dy)-0.38}] \
        [expr {$dx+0.38}] [expr {max($ty,$dy)+0.38}]
}
regcap_transition_35 227.0 276.4

# Preserve the front-end ports at their exact child landings.
regcap_port RXP metal3 -41.4 -56.0 -40.6 -54.0
regcap_port RXN metal3 -1.4 -56.0 -0.6 -54.0
set term_y {-117 -108 -99 -90 -81 -72 -63}
for {set index 0} {$index < 7} {incr index} {
    set y [lindex $term_y $index]
    regcap_port TERM_EN${index}_N metal4 -59.0 [expr {$y-0.40}] \
        -58.0 [expr {$y+0.40}]
}
regcap_port VTHP metal5 -23.5 33.0 -22.5 34.0
regcap_port VTHN metal5 -19.5 33.0 -18.5 34.0
regcap_port RX_BIAS metal4 -3.45 -46.0 -2.55 -43.5
regcap_port RX_BW_EN_N metal4 -4.0 22.92 -2.0 23.68
foreach {name x y} {
    E_SENSE_CLK -13 97.8 E_REGEN_CLK -189 148.0 E_REGEN_CLKB -191 149.4
    E_CAPTURE_CLK -193 144.0 E_CAPTURE_CLKB -195 145.4 E_SENSE_BOOST -15 99.2
    O_SENSE_CLK 45 97.8 O_REGEN_CLK 221 148.0 O_REGEN_CLKB 223 149.4
    O_CAPTURE_CLK 225 144.0 O_CAPTURE_CLKB 227 145.4 O_SENSE_BOOST 47 99.2
} {
    regcap_port $name metal5 [expr {$x-0.45}] [expr {$y-0.45}] \
        [expr {$x+0.45}] [expr {$y+0.45}]
}
regcap_port VDD metal5 -227 -147 -223 -143
regcap_port VSS metal4 -217 -137 -213 -133
regcap_port RX_RAWP metal4 9.02 42.0 9.78 45.0
regcap_port RX_RAWN metal3 20.22 42.0 20.98 45.0
regcap_port FE_E_P metal5 -191.45 141.75 -190.55 142.65
regcap_port FE_E_N metal5 -13.45 140.35 -12.55 141.25
regcap_port FE_O_P metal5 44.55 140.35 45.45 141.25
regcap_port FE_O_N metal5 222.55 141.75 223.45 142.65
regcap_port EVEN_Q metal5 -46.45 257.55 -45.55 258.45
regcap_port EVEN_QB metal5 -44.45 258.95 -43.55 259.85
regcap_port ODD_Q metal5 125.55 260.35 126.45 261.25
regcap_port ODD_QB metal5 127.55 261.75 128.45 262.65

save /work/lane_rx_regenerative_capture
gds write /work/lane_rx_regenerative_capture.gds
quit -noprompt
