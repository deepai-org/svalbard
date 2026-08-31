# SPDX-License-Identifier: Apache-2.0
# Probe-landing-level RF open/short/thru/load coupon for 2.4 GHz Wi-Fi work.
# A qualified pad/probe/package design must surround this die-side coupon.

proc rc_rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}
proc rc_via {layer x y} {
    rc_rect $layer [expr {$x-0.28}] [expr {$y-0.28}] \
        [expr {$x+0.28}] [expr {$y+0.28}]
}
proc rc_45 {x y} {
    foreach layer {metal4 metal5} {
        rc_rect $layer [expr {$x-0.55}] [expr {$y-0.55}] \
            [expr {$x+0.55}] [expr {$y+0.55}]
    }
    rc_via via4 $x $y
}
proc rc_stack15 {x y} {
    foreach layer {metal1 metal2 metal3 metal4 metal5} {
        rc_rect $layer [expr {$x-0.55}] [expr {$y-0.55}] \
            [expr {$x+0.55}] [expr {$y+0.55}]
    }
    foreach layer {via1 via2 via3 via4} { rc_via $layer $x $y }
}
set rc_port_number 1
proc rc_port {name x y} {
    global rc_port_number
    rc_rect metal5 [expr {$x-7.0}] [expr {$y-7.0}] \
        [expr {$x+7.0}] [expr {$y+7.0}]
    box values [expr {$x-7.0}] [expr {$y-7.0}] \
        [expr {$x+7.0}] [expr {$y+7.0}]
    label $name FreeSans 1.0 0 0 0 c metal5
    port make $rc_port_number
    incr rc_port_number
}
proc rc_datum {name x y} {
    rc_rect metal5 [expr {$x-7.0}] [expr {$y-7.0}] \
        [expr {$x+7.0}] [expr {$y+7.0}]
    box values [expr {$x-7.0}] [expr {$y-7.0}] \
        [expr {$x+7.0}] [expr {$y+7.0}]
    label $name FreeSans 1.0 0 0 0 c metal5
}
proc rc_gsg_ground {x y} {
    # Two local ground landings make the intended G-S-G probing geometry
    # inspectable without pretending these are qualified production pad cells.
    foreach dx {-18.0 18.0} {
        set gx [expr {$x+$dx}]
        rc_rect metal5 [expr {$gx-3.5}] [expr {$y-7.0}] \
            [expr {$gx+3.5}] [expr {$y+7.0}]
        rc_45 $gx [expr {$y-5.5}]
        rc_rect metal4 [expr {$gx-0.55}] 18.0 [expr {$gx+0.55}] \
            [expr {$y-5.5}]
    }
}

crashbackups stop
load wifi_rf_ostl_coupon_hier
units microns

# The load uses the same P+ poly construction and direct M1-to-M5
# terminal stacks already proven in the wireline calibration DAC. Its measured
# impedance, rather than the PDK nominal sheet resistance, is the standard.
set load_unit [magic::gencell_makecell gf180mcu::ppolyf_u \
    w 2 l 40 guard 1 full_metal 1]
getcell $load_unit child 0 0 parent 238 70
identify XLOAD
select top cell
flatten wifi_rf_ostl_coupon
load wifi_rf_ostl_coupon
units microns

rc_rect pwell 4 4 316 216

# Common reference plane.  Each local G-S-G ground landing descends through a
# controlled M5/M4 transition into this route; the signal landing does not.
rc_rect metal4 8 18 312 21
rc_rect metal5 8 8 312 12
rc_45 20 19.5
rc_port VSS 20 10

# A die-side thru replica uses the same M5/M4 transition family as the parent
# RF route.  The two names are datum labels on one intentional net, so they
# must not appear as separate LVS ports.
rc_datum THRU_A 48 178
rc_datum THRU_B 272 178
rc_gsg_ground 48 178
rc_gsg_ground 272 178
rc_rect metal5 48 175.5 272 180.5

# OPEN retains the complete landing and nearby grounds while its signal metal
# deliberately stops at the datum.  This measures landing/coupling parasitics.
rc_port OPEN 48 108
rc_gsg_ground 48 108

# SHORT uses the identical landing geometry and joins the central signal to the
# M4 reference plane at the datum.  It is a labelled physical standard, not an
# independent electrical port, because a real short aliases the reference net.
rc_datum SHORT 136 108
rc_gsg_ground 136 108
rc_45 136 102.5
rc_rect metal4 135.45 20.0 136.55 102.5

# LOAD has the same landing geometry, then a P+ poly unit. The M1-to-M5
# stacks land at its explicit l=40 um terminals (49.67 and 90.33 um here), so
# the physical device rather than a bench ideal is extracted.
rc_port LOAD 238 108
rc_gsg_ground 238 108
rc_stack15 238 90.33
rc_stack15 238 49.67
rc_rect metal5 237.45 90.33 238.55 108.0
rc_rect metal5 237.45 10.0 238.55 49.67

# The PDK extracts the third poly-resistor terminal as a distinct local body
# node. It is deliberately not hidden by an artificial metal short; the
# matching source calls it RES_BODY and the silicon plan characterizes it.

# Frequent substrate contacts give the coupon a real reference instead of a
# floating drawing. The resistor's separately extracted body is intentional.
rc_rect psubdiff 4 4 316 4.8
rc_rect psubdiff 4 215.2 316 216
rc_rect psubdiff 4 4 4.8 216
rc_rect psubdiff 315.2 4 316 216
rc_rect metal1 4 4 316 4.8
rc_rect metal1 4 215.2 316 216
rc_rect metal1 4 4 4.8 216
rc_rect metal1 315.2 4 316 216
foreach x {8 24 40 56 72 88 104 120 136 152 168 184 200 216 232 248 264 280 296 312} {
    rc_rect psubdiffcont [expr {$x-0.25}] 4.15 [expr {$x+0.25}] 4.65
    rc_rect psubdiffcont [expr {$x-0.25}] 215.35 [expr {$x+0.25}] 215.85
}
foreach y {20 36 52 68 84 100 116 132 148 164 180 196} {
    rc_rect psubdiffcont 4.15 [expr {$y-0.25}] 4.65 [expr {$y+0.25}]
    rc_rect psubdiffcont 315.35 [expr {$y-0.25}] 315.85 [expr {$y+0.25}]
}
rc_rect metal1 19.5 4.0 20.5 20.0
rc_rect metal2 19.5 4.0 20.5 20.0
rc_rect metal3 19.5 4.0 20.5 20.0
rc_rect metal4 19.5 4.0 20.5 20.0
foreach layer {via1 via2 via3} { rc_via $layer 20 10 }

save /work/wifi_rf_ostl_coupon
gds write /work/wifi_rf_ostl_coupon.gds
quit -noprompt
