# SPDX-License-Identifier: Apache-2.0
# Symmetric GF180 layout for the dual CML programmable-window error slicer.

proc paint_rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}
proc via_at {layer x y} {
    paint_rect $layer [expr {$x-0.18}] [expr {$y-0.18}] [expr {$x+0.18}] [expr {$y+0.18}]
}
proc stack_to {x y highest} {
    foreach layer {metal1 metal2} {
        paint_rect $layer [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]
    }
    via_at via1 $x $y
    if {$highest >= 3} {
        paint_rect metal3 [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]
        via_at via2 $x $y
    }
    if {$highest >= 4} {
        paint_rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]
        via_at via3 $x $y
    }
    if {$highest >= 5} {
        paint_rect metal5 [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]
        via_at via4 $x $y
    }
}
proc stack_from3_to {x y highest} {
    paint_rect metal3 [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]
    if {$highest >= 4} {
        via_at via3 $x $y
        paint_rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]
    }
    if {$highest >= 5} {
        via_at via4 $x $y
        paint_rect metal5 [expr {$x-0.38}] [expr {$y-0.38}] [expr {$x+0.38}] [expr {$y+0.38}]
    }
}
proc substrate_contact {x y} {
    paint_rect psubdiffcont [expr {$x-0.25}] [expr {$y-0.30}] [expr {$x+0.25}] [expr {$y+0.30}]
}
proc make_port {name number layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    label $name FreeSans 0.5 0 0 0 c $layer
    port make $number
}
proc mos_terminal_strap {cx cy yoff xs highest} {
    set y [expr {$cy+$yoff}]
    foreach xoff $xs {
        set x [expr {$cx+$xoff}]
        paint_rect metal1 [expr {$x-0.30}] [expr {$y-0.30}] [expr {$x+0.30}] [expr {$y+0.30}]
        via_at via1 $x $y
        if {$highest >= 3} { via_at via2 $x $y }
    }
    paint_rect metal2 [expr {$cx+[lindex $xs 0]-0.38}] [expr {$y-0.38}] \
        [expr {$cx+[lindex $xs end]+0.38}] [expr {$y+0.38}]
    if {$highest >= 3} {
        paint_rect metal3 [expr {$cx+[lindex $xs 0]-0.38}] [expr {$y-0.38}] \
            [expr {$cx+[lindex $xs end]+0.38}] [expr {$y+0.38}]
    }
}
proc manual_gate_bottom {cx y half_width xs} {
    paint_rect polysilicon [expr {$cx-$half_width}] $y [expr {$cx+$half_width}] [expr {$y+0.25}]
    foreach xoff $xs {
        set x [expr {$cx+$xoff}]
        paint_rect polysilicon [expr {$x-0.20}] [expr {$y-0.65}] [expr {$x+0.20}] [expr {$y+0.25}]
        paint_rect polycontact [expr {$x-0.115}] [expr {$y-0.565}] [expr {$x+0.115}] [expr {$y-0.335}]
    }
    paint_rect metal1 [expr {$cx+[lindex $xs 0]-0.35}] [expr {$y-0.65}] \
        [expr {$cx+[lindex $xs end]+0.35}] [expr {$y-0.05}]
}

crashbackups stop
load cml_error_slicer_hier
set main_cell [magic::gencell_makecell gf180mcu::nfet_03v3 w 8 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set threshold_cell [magic::gencell_makecell gf180mcu::nfet_03v3 w 8 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set main_tail [magic::gencell_makecell gf180mcu::nfet_03v3 w 8 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set threshold_tail [magic::gencell_makecell gf180mcu::nfet_03v3 w 8 l 0.28 nf 2 guard 0 topc 0 botc 0 full_metal 0]
set load_cell [magic::gencell_makecell gf180mcu::ppolyf_u w 2 l 4.00 guard 1 full_metal 1]

units microns
foreach {cell instance x y} [list \
        $main_cell XUMP -26 5 $main_cell XUMN -20 5 \
        $threshold_cell XUTP -14 5 $threshold_cell XUTN -8 5 \
        $threshold_cell XDTN 8 5 $threshold_cell XDTP 14 5 \
        $main_cell XDMN 20 5 $main_cell XDMP 26 5 \
        $main_tail XUMT -23 -12 $threshold_tail XUTT -11 -12 \
        $threshold_tail XDTT 11 -12 $main_tail XDMT 23 -12 \
        $load_cell XURN -21 21 $load_cell XURP -7 21 \
        $load_cell XDRP 7 21 $load_cell XDRN 21 21] {
    getcell $cell child 0 0 parent $x $y
    identify $instance
}

select top cell
flatten cml_error_slicer
load cml_error_slicer
units microns
paint_rect pwell -33 -29 33 30

# Mirrored UP/main, UP/threshold, DOWN/threshold, DOWN/main device row.
foreach x {-26 -20 -14 -8 8 14 20 26} {
    mos_terminal_strap $x 5 2.25 {-0.8 0.8} 3
    mos_terminal_strap $x 5 -2.25 {0.0} 3
    manual_gate_bottom $x 0.65 0.55 {-0.4 0.4}
}
foreach x {-23 -11 11 23} {
    mos_terminal_strap $x -12 2.25 {-0.8 0.8} 3
    mos_terminal_strap $x -12 -2.25 {0.0} 3
    manual_gate_bottom $x -16.35 0.55 {-0.4 0.4}
}

# Four compact pair-source nodes drop directly into their local tails.
foreach cx {-23 -11 11 23} {
    set left [expr {$cx-3}]
    set right [expr {$cx+3}]
    foreach x [list $left $right] { stack_from3_to $x 2.75 4 }
    paint_rect metal4 [expr {$left-0.38}] 2.37 [expr {$right+0.38}] 3.13
    paint_rect metal4 [expr {$cx-0.38}] -9.75 [expr {$cx+0.38}] 3.13
    stack_from3_to $cx -9.75 4
}

# Four separate output summing nets.  Alternating M4/M5 keeps crossings absent.
# UPN: drains -26,-8 to load -21.
foreach x {-26 -8} { stack_from3_to $x 7.25 5; paint_rect metal5 [expr {$x-0.38}] 7.25 [expr {$x+0.38}] 12.5 }
paint_rect metal5 -26.38 12.12 -7.62 12.88
paint_rect metal5 -21.38 12.5 -20.62 18.67
stack_to -21 18.67 5
# UPP: drains -20,-14 to load -7.
foreach x {-20 -14} { stack_from3_to $x 7.25 4; paint_rect metal4 [expr {$x-0.38}] 7.25 [expr {$x+0.38}] 10.5 }
paint_rect metal4 -20.38 10.12 -6.62 10.88
paint_rect metal4 -7.38 10.5 -6.62 18.67
stack_to -7 18.67 4
# DNP: drains 14,20 to load 7.
foreach x {14 20} { stack_from3_to $x 7.25 4; paint_rect metal4 [expr {$x-0.38}] 7.25 [expr {$x+0.38}] 10.5 }
paint_rect metal4 6.62 10.12 20.38 10.88
paint_rect metal4 6.62 10.5 7.38 18.67
stack_to 7 18.67 4
# DNN: drains 8,26 to load 21.
foreach x {8 26} { stack_from3_to $x 7.25 5; paint_rect metal5 [expr {$x-0.38}] 7.25 [expr {$x+0.38}] 12.5 }
paint_rect metal5 7.62 12.12 26.38 12.88
paint_rect metal5 20.62 12.5 21.38 18.67
stack_to 21 18.67 5
make_port UPP 9 metal4 -7.45 14.0 -6.55 15.4
make_port UPN 10 metal5 -21.45 14.0 -20.55 15.4
make_port DNP 11 metal4 6.55 14.0 7.45 15.4
make_port DNN 12 metal5 20.55 14.0 21.45 15.4

# Load tops and a wide central VDD rail.
foreach x {-21 -7 7 21} {
    stack_to $x 23.33 5
    paint_rect metal5 [expr {$x-0.45}] 23.33 [expr {$x+0.45}] 27.0
}
paint_rect metal5 -30 26.55 30 27.45
make_port VDD 7 metal5 -1 26.55 1 27.45

# Equalized paired input/reference routes.  Orthogonal layer assignment avoids
# silently shorting the four long matched nets at their crossings.
foreach x {-26 20} {
    stack_to $x 0.30 2
    paint_rect metal2 [expr {$x-0.38}] -23.38 [expr {$x+0.38}] 0.68
}
paint_rect metal2 -26.38 -23.38 20.38 -22.62
make_port ERRP 1 metal2 -26.45 -23.45 -25.1 -22.55
foreach x {-20 26} {
    stack_to $x 0.30 3
    paint_rect metal3 [expr {$x-0.38}] -25.38 [expr {$x+0.38}] 0.68
}
paint_rect metal3 -20.38 -25.38 26.38 -24.62
make_port ERRN 2 metal3 25.1 -25.45 26.45 -24.55

# Reference routes remain above the tail-bias region and use different layers.
foreach x {-14 14} {
    stack_to $x 0.30 5
    paint_rect metal5 [expr {$x-0.38}] -2.38 [expr {$x+0.38}] 0.68
}
paint_rect metal5 -14.38 -2.38 14.38 -1.62
make_port VREFP 3 metal5 -0.9 -2.45 0.9 -1.55
foreach x {-8 8} {
    stack_to $x 0.30 3
    paint_rect metal3 [expr {$x-0.38}] -4.38 [expr {$x+0.38}] 0.68
}
paint_rect metal3 -8.38 -4.38 8.38 -3.62
make_port VREFN 4 metal3 -0.9 -4.45 0.9 -3.55

# Independent main and threshold tail-bias rails provide silicon calibration.
foreach x {-23 23} {
    stack_to $x -16.70 4
    paint_rect metal4 [expr {$x-0.38}] -20.88 [expr {$x+0.38}] -16.70
}
paint_rect metal4 -29 -20.88 29 -20.12
make_port VBIAS_MAIN 5 metal4 -29 -20.88 -27.2 -20.12
foreach x {-11 11} { stack_to $x -16.70 5 }
paint_rect metal5 -11.38 -19.08 11.38 -18.32
foreach x {-11 11} { paint_rect metal5 [expr {$x-0.38}] -19.08 [expr {$x+0.38}] -16.70 }
make_port VBIAS_TH 6 metal5 -0.9 -19.08 0.9 -18.32

# Contacted substrate guard ring and symmetric tail-source returns.
paint_rect psubdiff -33 -29 -32.2 30
paint_rect psubdiff 32.2 -29 33 30
paint_rect psubdiff -33 -29 33 -28.2
paint_rect psubdiff -33 29.2 33 30
paint_rect metal1 -33 -29 -32.2 30
paint_rect metal1 32.2 -29 33 30
paint_rect metal1 -33 -29 33 -28.2
paint_rect metal1 -33 29.2 33 30
foreach x {-30 -24 -18 -12 -6 0 6 12 18 24 30} { substrate_contact $x -28.6; substrate_contact $x 29.6 }
foreach y {-26 -20 -14 -8 -2 4 10 16 22 28} { substrate_contact -32.6 $y; substrate_contact 32.6 $y }
foreach {x edge} {-23 -32.6 -11 -32.6 11 32.6 23 32.6} {
    stack_from3_to $x -14.25 4
    paint_rect metal4 [expr {min($x,$edge)-0.38}] -14.63 [expr {max($x,$edge)+0.38}] -13.87
    stack_to $edge -14.25 4
}
stack_to 32.6 -26.0 5
paint_rect metal5 32.22 -26.0 32.98 -14.25
make_port VSS 8 metal5 32.22 -26.0 32.98 -24.5

save /work/cml_error_slicer
gds write /work/cml_error_slicer.gds
quit -noprompt
