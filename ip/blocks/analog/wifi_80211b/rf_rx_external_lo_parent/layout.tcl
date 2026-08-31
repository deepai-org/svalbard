# SPDX-License-Identifier: Apache-2.0
# Parent-owned LNA-drain to mixer-RF interconnect with explicit external ports.
proc rfp_rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}
proc rfp_via {layer x y} {
    rfp_rect $layer [expr {$x-0.22}] [expr {$y-0.22}] \
        [expr {$x+0.22}] [expr {$y+0.22}]
}
proc rfp_transition_45 {x y} {
    foreach layer {metal4 metal5} {
        rfp_rect $layer [expr {$x-0.40}] [expr {$y-0.40}] \
            [expr {$x+0.40}] [expr {$y+0.40}]
    }
    rfp_via via4 $x $y
}
set rfp_port_number 1
proc rfp_port {name layer x y} {
    global rfp_port_number
    rfp_rect $layer [expr {$x-0.50}] [expr {$y-0.50}] \
        [expr {$x+0.50}] [expr {$y+0.50}]
    box values [expr {$x-0.50}] [expr {$y-0.50}] \
        [expr {$x+0.50}] [expr {$y+0.50}]
    label $name FreeSans 0.5 0 0 0 c $layer
    port make $rfp_port_number
    incr rfp_port_number
}

crashbackups stop
load wifi_rx_external_lo_parent_hier
units microns
getcell wifi_lna_cs_core child 0 0 parent 0 0
identify XLNA
getcell wifi_rf_switch_mixer child 0 0 parent 90 0
identify XMIX
select top cell
load wifi_rx_external_lo_parent_hier
units microns

# LNA RF_OUT is at (26.4,31); mixer RF_IN is at (130,6) after placement. The
# parent route leaves both sensitive cell interiors vertically, crosses on M5,
# and exposes one measured external-load landing on the same physical net.
rfp_transition_45 26.4 31.0
rfp_rect metal5 26.0 31.0 26.8 45.0
rfp_rect metal5 26.4 44.6 130.0 45.4
rfp_rect metal5 129.6 6.0 130.4 45.0
rfp_transition_45 130.0 6.0
rfp_port MIX_RF metal5 78.0 45.0

# Tie the two explicit body contacts with an owned wide VSS route. The parent
# has no hidden common ground through a testbench net name.
rfp_rect metal4 4.25 32.5 94.25 33.5

# Preserve all bench ports at their actual child landings.
rfp_port RF_GATE metal4 16.0 9.0
rfp_port LNA_SOURCE metal4 20.0 6.0
rfp_port LO metal4 112.0 9.0
rfp_port LOB metal4 148.0 9.0
rfp_port IFP metal4 118.0 31.0
rfp_port IFN metal4 142.0 31.0
rfp_port VSS metal4 4.25 33.0

save /work/wifi_rx_external_lo_parent
gds write /work/wifi_rx_external_lo_parent.gds
quit -noprompt
