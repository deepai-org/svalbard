# SPDX-License-Identifier: Apache-2.0
# First namespace-safe routed parent: event -> V7 fanout -> regenerative lane.

proc ep_rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}
proc ep_via {layer x y} {
    ep_rect $layer [expr {$x-0.18}] [expr {$y-0.18}] \
        [expr {$x+0.18}] [expr {$y+0.18}]
}
proc ep_transition_45 {x y} {
    ep_rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    ep_rect metal5 [expr {$x-0.38}] [expr {$y-0.38}] \
        [expr {$x+0.38}] [expr {$y+0.38}]
    ep_via via4 $x $y
}
proc ep_transition_34 {x y} {
    ep_rect metal3 [expr {$x-0.28}] [expr {$y-0.28}] \
        [expr {$x+0.28}] [expr {$y+0.28}]
    ep_rect metal4 [expr {$x-0.28}] [expr {$y-0.28}] \
        [expr {$x+0.28}] [expr {$y+0.28}]
    ep_via via3 $x $y
}
proc ep_transition_23 {x y} {
    ep_rect metal2 [expr {$x-0.28}] [expr {$y-0.28}] \
        [expr {$x+0.28}] [expr {$y+0.28}]
    ep_rect metal3 [expr {$x-0.28}] [expr {$y-0.28}] \
        [expr {$x+0.28}] [expr {$y+0.28}]
    ep_via via2 $x $y
}
proc ep_route_45 {sx sy dx dy track} {
    ep_rect metal4 [expr {$sx-0.28}] [expr {min($sy,$track)-0.28}] \
        [expr {$sx+0.28}] [expr {max($sy,$track)+0.28}]
    ep_transition_45 $sx $track
    ep_rect metal5 [expr {min($sx,$dx)-0.38}] [expr {$track-0.38}] \
        [expr {max($sx,$dx)+0.38}] [expr {$track+0.38}]
    ep_transition_45 $dx $track
    ep_rect metal4 [expr {$dx-0.28}] [expr {min($dy,$track)-0.28}] \
        [expr {$dx+0.28}] [expr {max($dy,$track)+0.28}]
    ep_transition_45 $dx $dy
}
# Route a source upward on Metal4, cross later destination trunks on Metal3,
# then descend to the destination on Metal4.  This is the safe fan-out form
# when several ordered source pins spread toward ordered destination pins:
# the parent supply rails remain on Metal4/Metal5, and the source/destination
# verticals cannot join the perpendicular Metal3 tracks without an explicit
# via at the intended endpoint.
proc ep_route_43_34 {sx sy dx dy track} {
    ep_transition_45 $sx $sy
    ep_rect metal4 [expr {$sx-0.28}] [expr {min($sy,$track)-0.28}] \
        [expr {$sx+0.28}] [expr {max($sy,$track)+0.28}]
    ep_transition_34 $sx $track
    ep_rect metal3 [expr {min($sx,$dx)-0.28}] [expr {$track-0.28}] \
        [expr {max($sx,$dx)+0.28}] [expr {$track+0.28}]
    ep_transition_34 $dx $track
    ep_rect metal4 [expr {$dx-0.28}] [expr {min($dy,$track)-0.28}] \
        [expr {$dx+0.28}] [expr {max($dy,$track)+0.28}]
    ep_transition_45 $dx $dy
}
proc ep_m5_bridge_x {x1 x2 y left right} {
    ep_rect metal5 $x1 [expr {$y-0.38}] [expr {$left+0.38}] [expr {$y+0.38}]
    ep_transition_45 $left $y
    ep_rect metal4 [expr {$left-0.28}] [expr {$y-0.28}] \
        [expr {$right+0.28}] [expr {$y+0.28}]
    ep_transition_45 $right $y
    ep_rect metal5 [expr {$right-0.38}] [expr {$y-0.38}] $x2 [expr {$y+0.38}]
}
set ep_port_number 1
proc ep_port {name layer x y size} {
    global ep_port_number
    set half [expr {$size/2.0}]
    ep_rect $layer [expr {$x-$half}] [expr {$y-$half}] \
        [expr {$x+$half}] [expr {$y+$half}]
    box values [expr {$x-$half}] [expr {$y-$half}] \
        [expr {$x+$half}] [expr {$y+$half}]
    label $name FreeSans 0.5 0 0 0 c $layer
    port make $ep_port_number
    incr ep_port_number
}

crashbackups stop
load event_lane_routed_parent_hier
units microns
getcell retimed_event_capture_bridge child 0 0 parent -750 0
identify XEVENT
getcell local_clock_fanout child 0 0 parent -410 0
identify XFANOUT
getcell lane_rx_regenerative_capture child 0 0 parent 0 0
identify XLANE
getcell capture_clock_bridge child 0 0 parent -110 350
identify XRESTORE_S
getcell capture_clock_bridge child 0 0 parent 0 350
identify XRESTORE_C
getcell capture_clock_bridge child 0 0 parent 110 350
identify XRESTORE_CB
select top cell
load event_lane_routed_parent_hier
units microns

set ep_route_signals 1
if {$ep_route_signals} {
# Event capture clocks into the V7 fanout. Tracks are above all child bboxes;
# Metal4 verticals and Metal5 horizontals cross without accidental junctions.
ep_transition_45 -456.780 109.000
ep_rect metal5 -457.160 108.620 -443.620 109.380
ep_transition_45 -444.000 109.000
ep_rect metal4 -444.280 -15.280 -443.720 109.280
ep_transition_45 -444.000 -15.000
ep_rect metal5 -444.380 -15.380 -434.620 -14.620
ep_transition_45 -435.000 -15.000
ep_rect metal4 -435.280 -15.280 -424.720 -14.720
ep_transition_45 -425.000 -15.000
ep_rect metal5 -425.380 -15.380 -397.060 -14.620
ep_transition_45 -397.440 -15.000
ep_transition_34 -397.440 -15.000
ep_rect metal3 -397.720 -15.280 -397.160 -3.720
ep_transition_34 -397.440 -4.000
ep_transition_45 -397.440 -4.000
ep_transition_45 -469.040 104.800
ep_rect metal5 -469.420 104.420 -442.120 105.180
ep_transition_45 -442.500 104.800
ep_rect metal4 -442.780 30.420 -442.220 105.080
ep_transition_45 -442.500 30.700
ep_rect metal5 -442.880 30.320 -434.620 31.080
ep_transition_45 -435.000 30.700
ep_rect metal4 -435.280 30.420 -424.720 30.980
ep_transition_45 -425.000 30.700
ep_rect metal5 -425.380 30.320 -413.620 31.080
ep_transition_45 -456.780 285.000
ep_rect metal5 -457.160 284.620 -443.620 285.380
ep_transition_45 -444.000 285.000
ep_rect metal4 -444.280 171.720 -443.720 285.280
ep_transition_45 -444.000 172.000
ep_rect metal5 -444.380 171.620 -397.060 172.380
ep_transition_45 -469.040 280.800
ep_rect metal5 -469.420 280.420 -442.120 281.180
ep_transition_45 -442.500 280.800
ep_rect metal4 -442.780 206.420 -442.220 281.080
ep_transition_45 -442.500 206.700
ep_rect metal5 -442.880 206.320 -417.620 207.080
# Remaining routes are admitted incrementally after LVS proves each escape.

# Legacy direct fanout outputs are retained as readable negative-history
# geometry but disabled.  The v2 parent inserts capture-owned restorers below.
set ep_route_legacy_outputs 0
if {$ep_route_legacy_outputs} {
# Fanout outputs into the independently clocked regenerative lane.
ep_rect metal4 -286.360 30.420 -264.720 30.980
ep_transition_45 -265.000 30.700
ep_rect metal5 -265.380 30.320 -259.620 31.080
ep_transition_45 -260.000 30.700
ep_rect metal4 -260.280 30.420 -259.720 98.080
ep_transition_45 -260.000 97.800
ep_m5_bridge_x -260.380 -12.620 97.800 -230.000 -220.000
set ep_route_e_capture 1
if {$ep_route_e_capture} {
ep_rect metal4 -339.480 30.420 -338.920 36.280
ep_rect metal4 -339.480 35.720 -324.720 36.280
ep_rect metal4 -325.280 35.720 -324.720 42.280
ep_rect metal4 -325.280 41.720 -266.720 42.280
ep_transition_45 -267.000 42.000
ep_rect metal5 -267.380 41.620 -258.120 42.380
ep_transition_45 -258.500 42.000
ep_rect metal4 -258.780 41.720 -258.220 144.280
ep_transition_45 -258.500 144.000
ep_m5_bridge_x -258.880 -192.620 144.000 -230.000 -220.000
}
set ep_route_e_capture_b 1
if {$ep_route_e_capture_b} {
ep_rect metal4 -353.240 38.820 -352.680 45.280
ep_transition_45 -352.960 45.000
ep_rect metal5 -353.340 44.620 -256.620 45.380
ep_transition_45 -257.000 45.000
ep_rect metal4 -257.280 44.720 -256.720 145.680
ep_transition_45 -257.000 145.400
ep_m5_bridge_x -257.380 -194.620 145.400 -230.000 -220.000
}

set ep_route_o_sense 1
if {$ep_route_o_sense} {
ep_rect metal4 -286.360 206.420 -264.720 206.980
ep_transition_45 -265.000 206.700
ep_rect metal5 -265.380 206.320 -259.620 207.080
ep_transition_45 -260.000 206.700
ep_rect metal4 -260.280 102.720 -259.720 206.980
ep_transition_45 -260.000 103.000
ep_m5_bridge_x -260.380 45.380 103.000 -230.000 -220.000
ep_rect metal5 44.620 97.420 45.380 103.380
}

set ep_route_o_capture 1
if {$ep_route_o_capture} {
ep_transition_34 -339.200 206.700
ep_transition_23 -339.200 206.700
ep_rect metal2 -339.480 204.220 -338.920 206.980
ep_rect metal2 -339.480 204.220 -254.720 204.780
ep_transition_23 -255.000 204.500
ep_transition_34 -255.000 204.500
ep_transition_45 -255.000 204.500
ep_rect metal5 -255.380 204.120 -254.620 370.380
ep_rect metal5 -255.380 369.620 280.380 370.380
ep_transition_45 280.000 370.000
ep_rect metal4 279.720 143.720 280.280 370.280
ep_transition_45 280.000 144.000
ep_transition_34 280.000 144.000
ep_transition_23 280.000 144.000
ep_rect metal2 224.720 143.720 280.280 144.280
ep_transition_23 225.000 144.000
ep_transition_34 225.000 144.000
ep_transition_45 225.000 144.000
}
set ep_route_o_capture_b 1
if {$ep_route_o_capture_b} {
ep_rect metal4 -353.240 214.820 -352.680 217.780
ep_transition_34 -352.960 217.500
ep_transition_23 -352.960 217.500
ep_rect metal2 -353.240 217.220 -252.220 217.780
ep_transition_23 -252.500 217.500
ep_transition_34 -252.500 217.500
ep_transition_45 -252.500 217.500
ep_rect metal5 -252.880 217.120 -252.120 365.380
ep_transition_45 -252.500 365.000
ep_rect metal4 -252.780 364.720 -252.220 375.280
ep_transition_45 -252.500 375.000
ep_rect metal5 -252.880 374.620 -252.120 380.380
ep_rect metal5 -252.880 379.620 290.380 380.380
ep_transition_45 290.000 380.000
ep_rect metal4 289.720 145.120 290.280 380.280
ep_transition_45 290.000 145.400
ep_transition_34 290.000 145.400
ep_transition_23 290.000 145.400
ep_rect metal2 226.720 145.120 290.280 145.680
ep_transition_23 227.000 145.400
ep_transition_34 227.000 145.400
ep_transition_45 227.000 145.400
}
}
}

# V2 capture-owned restore bank.  Long routes terminate on light WRITE inputs;
# strong same-polarity CLK outputs escape each bridge at its outer edge before
# descending to the lane, avoiding the bridge's Metal4 VDD rail.
set ep_route_local_restore 1
if {$ep_route_local_restore} {
# Remote fanout outputs to light local-restore inputs.  O_CAPTURE_CLK is a
# native Metal3 pin; promote it before using the common M4/M5 route helper.
# EVEN SENSE: native M4 escape, M5 jog beyond the fanout obstruction, then M4.
ep_rect metal4 -286.36 30.42 -264.72 30.98
ep_transition_45 -265.0 30.70
ep_rect metal5 -265.38 30.32 -259.62 31.08
ep_transition_45 -260.0 30.70
ep_route_43_34 -260.0 30.70 -165.0 344.0 445.0
ep_rect metal5 -165.38 343.62 -159.62 344.38
# EVEN capture CLK.
ep_rect metal4 -339.48 30.42 -338.92 36.28
ep_rect metal4 -339.48 35.72 -324.72 36.28
ep_rect metal4 -325.28 35.72 -324.72 42.28
ep_rect metal4 -325.28 41.72 -266.72 42.28
ep_transition_45 -267.0 42.0
ep_rect metal5 -267.38 41.62 -258.12 42.38
ep_transition_45 -258.5 42.0
ep_route_43_34 -258.5 42.0 -55.0 344.0 447.0
ep_rect metal5 -55.38 343.62 -49.62 344.38
# EVEN capture CLKB.
ep_rect metal4 -353.24 38.82 -352.68 45.28
ep_transition_45 -352.96 45.0
ep_rect metal5 -353.34 44.62 -256.62 45.38
ep_transition_45 -257.0 45.0
ep_route_43_34 -257.0 45.0 55.0 344.0 449.0
ep_rect metal5 54.62 343.62 60.38 344.38
# ODD SENSE uses a separate clear-gap column.
ep_rect metal4 -286.36 206.42 -264.72 206.98
ep_transition_45 -265.0 206.70
ep_rect metal5 -265.38 206.32 -261.62 207.08
ep_transition_45 -262.0 206.70
ep_route_43_34 -262.0 206.70 -53.0 351.0 451.0
ep_rect metal5 -60.38 350.62 -52.62 351.38
# ODD capture CLK reuses the independently LVS-clean legacy Metal2 escape.
ep_transition_34 -339.20 206.70
ep_transition_23 -339.20 206.70
ep_rect metal2 -339.48 204.22 -338.92 206.98
ep_rect metal2 -339.48 204.22 -254.72 204.78
ep_transition_23 -255.0 204.50
ep_transition_34 -255.0 204.50
ep_transition_45 -255.0 204.50
ep_route_43_34 -255.0 204.50 57.0 351.0 453.0
ep_rect metal5 49.62 350.62 57.38 351.38
# ODD capture CLKB uses a third distinct clear-gap column.
ep_rect metal4 -353.24 214.82 -352.68 217.78
ep_transition_45 -352.96 217.50
ep_rect metal5 -353.34 217.12 -244.62 217.88
ep_transition_45 -245.0 217.50
ep_route_43_34 -245.0 217.50 165.0 351.0 455.0
ep_rect metal5 159.62 350.62 165.38 351.38

# EVEN SENSE output: local pin (-158,377), outer escape (-167,377), lane
# landing (-260,97.8), then the existing Metal5/Metal4 ring bridge.
ep_rect metal5 -260.38 97.42 -242.62 98.18
ep_transition_45 -243.0 97.8
ep_route_45 -243.0 97.8 -167.0 377.0 433.0
ep_rect metal5 -167.38 376.62 -157.62 377.38
ep_m5_bridge_x -260.38 -12.62 97.8 -230.0 -220.0

# EVEN capture clock and complement.
ep_rect metal5 -258.88 143.62 -240.62 144.38
ep_transition_45 -241.0 144.0
ep_route_45 -241.0 144.0 -57.0 377.0 435.0
ep_rect metal5 -57.38 376.62 -47.62 377.38
ep_m5_bridge_x -258.88 -192.62 144.0 -230.0 -220.0
ep_rect metal5 -257.38 145.02 -238.62 145.78
ep_transition_45 -239.0 145.4
ep_route_45 -239.0 145.4 53.0 377.0 437.0
ep_rect metal5 52.62 376.62 62.38 377.38
ep_m5_bridge_x -257.38 -194.62 145.4 -230.0 -220.0

# ODD SENSE output and outer-ring bridge into its interior Metal5 pin.
ep_rect metal5 -260.38 102.62 -236.62 103.38
ep_transition_45 -237.0 103.0
ep_route_45 -237.0 103.0 -51.0 385.0 439.0
ep_rect metal5 -62.38 384.62 -50.62 385.38
ep_m5_bridge_x -260.38 45.38 103.0 -230.0 -220.0
ep_rect metal5 44.62 97.42 45.38 103.38

# ODD capture outputs use the proven lower-metal crossings at the lane edge.
# The x=51 destination column passes beside the center restore's VDD port at
# y=426.  Cross that local obstruction on Metal3, with vias well outside the
# port enclosure, while retaining the proven Metal4/Metal5 outer route.
ep_rect metal4 279.72 143.72 280.28 441.28
ep_transition_45 280.0 441.0
ep_rect metal5 50.62 440.62 280.38 441.38
ep_transition_45 51.0 441.0
ep_rect metal4 50.72 428.72 51.28 441.28
ep_transition_34 51.0 429.0
ep_rect metal3 50.72 422.72 51.28 429.28
ep_transition_34 51.0 423.0
ep_rect metal4 50.72 384.72 51.28 423.28
ep_transition_45 51.0 385.0
ep_rect metal5 47.62 384.62 51.38 385.38
ep_transition_34 280.0 144.0
ep_transition_23 280.0 144.0
ep_rect metal2 224.72 143.72 280.28 144.28
ep_transition_23 225.0 144.0
ep_transition_34 225.0 144.0
ep_transition_45 225.0 144.0
ep_route_45 290.0 145.4 167.0 385.0 443.0
ep_rect metal5 157.62 384.62 167.38 385.38
ep_transition_34 290.0 145.4
ep_transition_23 290.0 145.4
ep_rect metal2 226.72 145.12 290.28 145.68
ep_transition_23 227.0 145.4
ep_transition_34 227.0 145.4
ep_transition_45 227.0 145.4
}

# Shared supplies use wide parent-owned Metal5 trunks below the children.
set ep_route_supplies 1
set ep_route_restore_power 1
if {$ep_route_supplies} {
set ep_route_vdd 1
if {$ep_route_vdd} {
ep_rect metal5 -773 -174 -222 -168
foreach x {-770 -430 -225} {
    ep_rect metal5 [expr {$x-3}] -171 [expr {$x+3}] 166
}
if {$ep_route_restore_power} {
# Local-restore VDD ports are at (-60,426), (50,426), and (160,426).
ep_rect metal5 -228 160 -222 429
ep_rect metal5 -225 423 -60 429
ep_rect metal5 -63 423 -57 426.6
ep_rect metal5 -60.4 425.4 160.4 426.6
}
}
set ep_route_vss 1
if {$ep_route_vss} {
ep_rect metal4 -781 -184 -214 -178
ep_rect metal5 -781 127.5 -775 131.5
ep_transition_45 -778 128
ep_rect metal4 -781 -181 -775 128
ep_rect metal5 -441 127.5 -435 131.5
ep_transition_45 -438 128
ep_rect metal4 -438.38 -181 -437.62 128
ep_rect metal4 -217.38 -181 -216.62 -135
if {$ep_route_restore_power} {
# Local-restore VSS ports are at (-160,337), (-50,337), and (60,337).
ep_rect metal4 -217.38 -181 -216.62 337.38
ep_transition_34 -217.0 337.0
ep_rect metal3 -217.28 336.72 60.28 337.28
foreach x {-160 -50 60} {
    ep_transition_34 $x 337.0
    ep_transition_45 $x 337.0
}
}
}
}

# Preserve external ports at exact child landings.
ep_port CLKP_H metal5 -746 -4 0.96
ep_port CLKN_H metal5 -746 172 0.96
ep_port SEL0 metal5 -756 127.1 0.96
ep_port SEL1 metal5 -758 122.9 0.96
ep_port SEL2 metal5 -760 120.8 0.96
ep_port RXP metal3 -41 -55 0.8
ep_port RXN metal3 -1 -55 0.8
set term_y {-117 -108 -99 -90 -81 -72 -63}
for {set index 0} {$index < 7} {incr index} {
    ep_port TERM_EN${index}_N metal4 -58.5 [lindex $term_y $index] 0.8
}
ep_port VTHP metal5 -23 33.5 0.8
ep_port VTHN metal5 -19 33.5 0.8
ep_port RX_BIAS metal4 -3 -44.75 0.8
ep_port RX_BW_EN_N metal4 -3 23.3 0.8
ep_port E_REGEN_CLK metal5 -189 148.0 0.9
ep_port E_REGEN_CLKB metal5 -191 149.4 0.9
ep_port E_SENSE_BOOST metal5 -15 99.2 0.9
ep_port O_REGEN_CLK metal5 221 148.0 0.9
ep_port O_REGEN_CLKB metal5 223 149.4 0.9
ep_port O_SENSE_BOOST metal5 47 99.2 0.9
ep_port VDD metal5 -770 -171 6.0
ep_port VSS metal4 -778 -181 6.0
ep_port RX_RAWP metal4 9.4 43.5 0.76
ep_port RX_RAWN metal3 20.6 43.5 0.76
ep_port FE_E_P metal5 -191 142.2 0.8
ep_port FE_E_N metal5 -13 140.8 0.8
ep_port FE_O_P metal5 45 140.8 0.8
ep_port FE_O_N metal5 223 142.2 0.8
ep_port EVEN_Q metal5 -46 258 0.8
ep_port EVEN_QB metal5 -44 259.4 0.8
ep_port ODD_Q metal5 126 260.8 0.8
ep_port ODD_QB metal5 128 262.2 0.8

save /work/event_lane_routed_parent
gds write /work/event_lane_routed_parent.gds
quit -noprompt
