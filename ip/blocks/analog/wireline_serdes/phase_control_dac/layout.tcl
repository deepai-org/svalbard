# SPDX-License-Identifier: Apache-2.0
# Symmetric GF180 dual 5-bit R-2R phase-control DAC.

proc paint_rect {layer x1 y1 x2 y2} { box values $x1 $y1 $x2 $y2; paint $layer }
proc via_at {layer x y} { paint_rect $layer [expr {$x-0.18}] [expr {$y-0.18}] [expr {$x+0.18}] [expr {$y+0.18}] }
proc stack_to {x y highest} {
    paint_rect metal1 [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]
    if {$highest >= 2} { paint_rect metal2 [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]; via_at via1 $x $y }
    if {$highest >= 3} { paint_rect metal3 [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]; via_at via2 $x $y }
    if {$highest >= 4} { paint_rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]; via_at via3 $x $y }
    if {$highest >= 5} { paint_rect metal5 [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]; via_at via4 $x $y }
}
proc stack_from3_to {x y highest} {
    paint_rect metal3 [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]
    if {$highest >= 4} { paint_rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]; via_at via3 $x $y }
    if {$highest >= 5} { paint_rect metal5 [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]; via_at via4 $x $y }
}
proc substrate_contact {x y} { paint_rect psubdiffcont [expr {$x-0.25}] [expr {$y-0.30}] [expr {$x+0.25}] [expr {$y+0.30}] }
proc make_port {name number layer x1 y1 x2 y2} { box values $x1 $y1 $x2 $y2; label $name FreeSans 0.5 0 0 0 c $layer; port make $number }
proc mos_terminal_strap {cx cy yoff xs} {
    set y [expr {$cy+$yoff}]
    foreach xoff $xs {
        set x [expr {$cx+$xoff}]
        paint_rect metal1 [expr {$x-0.30}] [expr {$y-0.30}] [expr {$x+0.30}] [expr {$y+0.30}]
        via_at via1 $x $y; via_at via2 $x $y
    }
    paint_rect metal2 [expr {$cx+[lindex $xs 0]-0.38}] [expr {$y-0.38}] [expr {$cx+[lindex $xs end]+0.38}] [expr {$y+0.38}]
    paint_rect metal3 [expr {$cx+[lindex $xs 0]-0.38}] [expr {$y-0.38}] [expr {$cx+[lindex $xs end]+0.38}] [expr {$y+0.38}]
}
proc manual_gate_bottom {cx y} {
    paint_rect polysilicon [expr {$cx-0.55}] $y [expr {$cx+0.55}] [expr {$y+0.25}]
    foreach xoff {-0.4 0.4} {
        set x [expr {$cx+$xoff}]
        paint_rect polysilicon [expr {$x-0.20}] [expr {$y-0.65}] [expr {$x+0.20}] [expr {$y+0.25}]
        paint_rect polycontact [expr {$x-0.115}] [expr {$y-0.565}] [expr {$x+0.115}] [expr {$y-0.335}]
    }
    paint_rect metal1 [expr {$cx-0.75}] [expr {$y-0.65}] [expr {$cx+0.75}] [expr {$y-0.05}]
}
proc resistor_terminal {x y layer} { stack_to $x $y $layer }

crashbackups stop
load phase_control_dac_hier
set sw [magic::gencell_makecell gf180mcu::nfet_03v3 w 8 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set rcell [magic::gencell_makecell gf180mcu::ppolyf_u w 2 l 20.00 guard 1 full_metal 1]
set r2cell [magic::gencell_makecell gf180mcu::ppolyf_u w 2 l 40.00 guard 1 full_metal 1]
units microns

# Place one proven nf=2 unit for each logical switch.
set switch_specs {}
foreach {ch bit cx dir} {A 4 -76 -1 A 3 -61 -1 A 2 -46 -1 A 1 -31 -1 A 0 -16 -1 B 4 76 1 B 3 61 1 B 2 46 1 B 1 31 1 B 0 16 1} {
    foreach {kind cy} {H 0 L -16} {
        getcell $sw child 0 0 parent $cx $cy
        identify X${ch}${bit}${kind}
        lappend switch_specs [list $cx $cy]
    }
}

# Five shunts plus one termination per channel, and four series units.
foreach {name x} {XA4R -76 XA3R -61 XA2R -46 XA1R -31 XA0R -16 XATR -5 XB0R 16 XB1R 31 XB2R 46 XB3R 61 XB4R 76 XBTR 5} {
    getcell $r2cell child 0 0 parent $x 42; identify $name
}
foreach {name x} {XAR0 -68.5 XAR1 -53.5 XAR2 -38.5 XAR3 -23.5 XBR0 68.5 XBR1 53.5 XBR2 38.5 XBR3 23.5} {
    getcell $rcell child 0 0 parent $x 76; identify $name
}

select top cell; flatten phase_control_dac; load phase_control_dac; units microns
paint_rect pwell -85 -38 85 98

# Contact every switch terminal and gate using the proven 8 um unit geometry.
foreach spec $switch_specs {
    lassign $spec x y
    mos_terminal_strap $x $y 2.25 {-0.8 0.8}; mos_terminal_strap $x $y -2.25 {0.0}
    manual_gate_bottom $x [expr {$y-4.35}]
}

# Per-bit branch risers and separate gate escapes.
set port_number 1
foreach {ch bit cx dir} {A 4 -76 -1 A 3 -61 -1 A 2 -46 -1 A 1 -31 -1 A 0 -16 -1 B 4 76 1 B 3 61 1 B 2 46 1 B 1 31 1 B 0 16 1} {
    stack_from3_to $cx 2.25 4; stack_from3_to $cx -13.75 4
    paint_rect metal4 [expr {$cx-0.38}] -13.75 [expr {$cx+0.38}] 21.67
    stack_to $cx 21.67 4

    set high_escape [expr {$cx+$dir*1.2}]
    set low_escape [expr {$cx-$dir*1.2}]
    paint_rect metal1 [expr {min($cx,$high_escape)-0.38}] -5.08 [expr {max($cx,$high_escape)+0.38}] -4.32
    stack_to $high_escape -4.70 5
    paint_rect metal5 [expr {$high_escape-0.38}] -30.0 [expr {$high_escape+0.38}] -4.32
    make_port ${ch}${bit} $port_number metal5 [expr {$high_escape-0.45}] -30.0 [expr {$high_escape+0.45}] -28.8
    incr port_number

    paint_rect metal1 [expr {min($cx,$low_escape)-0.38}] -21.08 [expr {max($cx,$low_escape)+0.38}] -20.32
    stack_to $low_escape -20.70 4
    paint_rect metal4 [expr {$low_escape-0.38}] -34.0 [expr {$low_escape+0.38}] -20.32
    make_port ${ch}${bit}B $port_number metal4 [expr {$low_escape-0.45}] -34.0 [expr {$low_escape+0.45}] -32.8
    incr port_number
}

# Shared quiet references; branch risers cross them on M4 without vias.
paint_rect metal3 -82 -2.63 82 -1.87
paint_rect metal3 -82 -18.63 82 -17.87
make_port VREFH 21 metal3 -1.0 -2.63 1.0 -1.87
make_port VREFL 22 metal3 -1.0 -18.63 1.0 -17.87

# R-2R nodes use descending metal layers from output (M5) to LSB (M1).
proc route_ladder {bit_x series_x terminal_x output_name output_port} {
    for {set k 0} {$k < 5} {incr k} {
        set layer [lindex {5 4 3 2 5} $k]; set metal metal$layer; set sx [lindex $bit_x $k]
        set xs [list $sx]
        resistor_terminal $sx 62.33 $layer
        paint_rect $metal [expr {$sx-0.38}] 62.33 [expr {$sx+0.38}] 64.38
        if {$k < 4} {
            set tx [lindex $series_x $k]
            set escape [expr {$tx + ($tx < 0 ? 1.5 : -1.5)}]
            lappend xs $escape
            resistor_terminal $tx 86.33 $layer
            paint_rect $metal [expr {min($tx,$escape)-0.38}] 85.95 [expr {max($tx,$escape)+0.38}] 86.71
            paint_rect $metal [expr {$escape-0.38}] 64.0 [expr {$escape+0.38}] 86.33
        }
        if {$k > 0} {
            set bx [lindex $series_x [expr {$k-1}]]; lappend xs $bx
            resistor_terminal $bx 65.67 $layer
            paint_rect $metal [expr {$bx-0.38}] 64.0 [expr {$bx+0.38}] 65.67
        }
        if {$k == 4} {
            lappend xs $terminal_x; resistor_terminal $terminal_x 62.33 $layer
            paint_rect $metal [expr {$terminal_x-0.38}] 62.33 [expr {$terminal_x+0.38}] 64.38
        }
        set xmin [lindex [lsort -real $xs] 0]; set xmax [lindex [lsort -real $xs] end]
        paint_rect $metal [expr {$xmin-0.38}] 64.0 [expr {$xmax+0.38}] 64.76
        if {$k == 0} { make_port $output_name $output_port $metal [expr {$sx-0.45}] 62.5 [expr {$sx+0.45}] 63.7 }
    }
}
route_ladder {-76 -61 -46 -31 -16} {-68.5 -53.5 -38.5 -23.5} -5 CTRL_A 24
route_ladder {76 61 46 31 16} {68.5 53.5 38.5 23.5} 5 CTRL_B 25

# Termination bottoms return to VREFL on M5, crossing VREFH without a via.
foreach x {-5 5} {
    stack_to $x 21.67 5
    paint_rect metal5 [expr {$x-0.38}] -18.25 [expr {$x+0.38}] 21.67
    stack_from3_to $x -18.25 5
}

# Contacted outer substrate guard supplies all switch bodies and resistor guards.
paint_rect psubdiff -85 -38 -84.2 98; paint_rect psubdiff 84.2 -38 85 98
paint_rect psubdiff -85 -38 85 -37.2; paint_rect psubdiff -85 97.2 85 98
paint_rect metal1 -85 -38 -84.2 98; paint_rect metal1 84.2 -38 85 98
paint_rect metal1 -85 -38 85 -37.2; paint_rect metal1 -85 97.2 85 98
foreach x {-82 -74 -66 -58 -50 -42 -34 -26 -18 -10 -2 6 14 22 30 38 46 54 62 70 78 82} { substrate_contact $x -37.6; substrate_contact $x 97.6 }
foreach y {-34 -26 -18 -10 -2 6 14 22 30 38 46 54 62 70 78 86 94} { substrate_contact -84.6 $y; substrate_contact 84.6 $y }
stack_to 84.6 -35.5 5
paint_rect metal5 84.22 -35.5 84.98 -18.0
make_port VSS 23 metal5 84.22 -35.5 84.98 -34.0

save /work/phase_control_dac
gds write /work/phase_control_dac.gds
quit -noprompt
