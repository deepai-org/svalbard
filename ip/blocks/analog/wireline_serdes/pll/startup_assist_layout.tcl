# SPDX-License-Identifier: Apache-2.0
# Symmetric matched pull-down pair for deterministic CML VCO startup.

proc rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}

proc via {layer x y} {
    rect $layer [expr {$x-0.18}] [expr {$y-0.18}] \
        [expr {$x+0.18}] [expr {$y+0.18}]
}

proc stack {x y highest} {
    foreach layer {metal1 metal2} {
        rect $layer [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
    }
    via via1 $x $y
    if {$highest >= 3} {
        rect metal3 [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
        via via2 $x $y
    }
    if {$highest >= 4} {
        rect metal4 [expr {$x-0.38}] [expr {$y-0.38}] \
            [expr {$x+0.38}] [expr {$y+0.38}]
        via via3 $x $y
    }
}

proc terminal {cx yoff xoff highest} {
    set x [expr {$cx+$xoff}]
    rect metal1 [expr {$x-0.28}] [expr {min(0,$yoff)-0.28}] \
        [expr {$x+0.28}] [expr {max(0,$yoff)+0.28}]
    via via1 $x $yoff
    rect metal2 [expr {$x-0.38}] [expr {$yoff-0.38}] \
        [expr {$x+0.38}] [expr {$yoff+0.38}]
    if {$highest >= 3} {
        via via2 $x $yoff
        rect metal3 [expr {$x-0.38}] [expr {$yoff-0.38}] \
            [expr {$x+0.38}] [expr {$yoff+0.38}]
    }
    if {$highest >= 4} {
        via via3 $x $yoff
        rect metal4 [expr {$x-0.38}] [expr {$yoff-0.38}] \
            [expr {$x+0.38}] [expr {$yoff+0.38}]
    }
}

proc gate_bottom {cx bridge_y} {
    set contact_y -2.35
    rect polysilicon [expr {$cx-0.55}] $bridge_y \
        [expr {$cx+0.55}] [expr {$bridge_y+0.25}]
    rect polysilicon [expr {$cx-0.20}] [expr {$contact_y-0.65}] \
        [expr {$cx+0.20}] [expr {$bridge_y+0.25}]
    rect polycontact [expr {$cx-0.115}] [expr {$contact_y-0.565}] \
        [expr {$cx+0.115}] [expr {$contact_y-0.335}]
    foreach layer {metal1 metal2 metal3 metal4} {
        rect $layer [expr {$cx-0.35}] [expr {$contact_y-0.65}] \
            [expr {$cx+0.35}] [expr {$contact_y-0.05}]
    }
    via via1 $cx [expr {$contact_y-0.35}]
    via via2 $cx [expr {$contact_y-0.35}]
    via via3 $cx [expr {$contact_y-0.35}]
    return [expr {$contact_y-0.35}]
}

proc make_port {name number layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    label $name FreeSans 0.5 0 0 0 c $layer
    port make $number
}

proc substrate_contact {x y} {
    rect psubdiffcont [expr {$x-0.25}] [expr {$y-0.30}] \
        [expr {$x+0.25}] [expr {$y+0.30}]
}

crashbackups stop
set cell cml_vco_startup_assist
set kick_w 1.0
load ${cell}_hier
set kick_device [magic::gencell_makecell gf180mcu::nfet_03v3 \
    w $kick_w l 0.28 nf 1 guard 0 topc 0 botc 0 full_metal 0]
units microns
foreach {instance x} {XKP -4 XKN 4} {
    getcell $kick_device child 0 0 parent $x 0
    identify $instance
}
select top cell
flatten $cell
load $cell
units microns
rect pwell -11 -8 11 7

# Matched drains rise locally to separate M4 node ports.
terminal -4 1.0 -0.4 4
terminal 4 1.0 -0.4 4
rect metal4 -10 0.62 -4.02 1.38
rect metal4 3.98 0.62 10 1.38
make_port NODEP 1 metal4 -10 0.55 -8.5 1.45
make_port NODEN 2 metal4 8.5 0.55 10 1.45

# Matched sources join one compact M3 VSS rail.  The escape sits far enough
# below the smaller PCell's internal contacts to preserve via spacing.
terminal -4 -1.4 0.4 3
terminal 4 -1.4 0.4 3
rect metal3 -3.98 -1.85 4.78 -0.95
make_port VSS 5 metal3 -0.8 -1.85 0.8 -0.95

# Independent kick gates escape downward on matched M4 routes.
set gate_contact_y [expr {-$kick_w/2.0-0.35}]
set gate_y_p [gate_bottom -4 $gate_contact_y]
set gate_y_n [gate_bottom 4 $gate_contact_y]
rect metal4 -4.38 -6.5 -3.62 [expr {$gate_y_p+0.30}]
rect metal4 3.62 -6.5 4.38 [expr {$gate_y_n+0.30}]
make_port KICKP 3 metal4 -4.45 -6.5 -3.55 -5.2
make_port KICKN 4 metal4 3.55 -6.5 4.45 -5.2

# Contacted substrate guard surrounds the pair without crossing signal ports.
rect psubdiff -11 -8 -10.2 7
rect psubdiff 10.2 -8 11 7
rect psubdiff -11 -8 11 -7.2
rect psubdiff -11 6.2 11 7
rect metal1 -11 -8 -10.2 7
rect metal1 10.2 -8 11 7
rect metal1 -11 -8 11 -7.2
rect metal1 -11 6.2 11 7
foreach x {-8 -4 0 4 8} {
    substrate_contact $x -7.6
    substrate_contact $x 6.6
}
foreach y {-5 -2 1 4} {
    substrate_contact -10.6 $y
    substrate_contact 10.6 $y
}
stack 0 -7.5 3
rect metal3 -0.38 -7.88 0.38 -1.4

save $cell
gds write /work/${cell}.gds
quit -noprompt
