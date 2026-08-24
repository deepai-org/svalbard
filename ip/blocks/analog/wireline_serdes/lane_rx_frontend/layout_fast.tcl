# SPDX-License-Identifier: Apache-2.0
# Fast-converter parent routing variant. Keep the historical parent generator
# immutable, then move the two data trunks that would cross the fast cell's
# full-width VSS mesh on the same metal layer.

set common_file /src/lane_rx_frontend/layout.tcl
set stream [open $common_file r]
set common_script [read $stream]
close $stream
regsub {quit -noprompt[ \t\r\n]*$} $common_script {} common_script
eval $common_script

select top cell
units microns

proc fast_front_erase {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    erase $layer
}
proc fast_front_rect {layer x1 y1 x2 y2} {
    box values $x1 $y1 $x2 $y2
    paint $layer
}

# The mirrored even cell spans x=-172..18 um and the odd cell spans
# x=64..254 um. Move the affected vertical M5 runs just outside those bounds;
# the short horizontal landings remain above the local y=322 um VSS mesh.
fast_front_erase metal5 6.62 275.12 7.38 338.78
fast_front_erase metal5 6.62 338.02 14.38 338.78
fast_front_rect metal5 6.62 275.12 7.38 284.38
fast_front_rect metal5 6.62 278.62 21.38 279.38
fast_front_rect metal5 20.62 278.62 21.38 335.50
front_transition_45 21.0 335.5
fast_front_rect metal4 20.62 335.12 21.38 339.88
front_transition_45 21.0 339.5
fast_front_rect metal5 20.62 339.12 21.38 343.38
fast_front_rect metal5 13.62 342.62 21.38 343.38
fast_front_rect metal5 13.62 338.02 14.38 343.38
fast_front_rect metal5 6.55 281.0 7.45 284.0
front_via via4 7.0 275.5

fast_front_erase metal5 74.62 275.12 75.38 338.78
fast_front_erase metal5 67.62 338.02 75.38 338.78
fast_front_rect metal5 74.62 275.12 75.38 284.38
fast_front_rect metal5 60.62 278.62 75.38 279.38
fast_front_rect metal5 60.62 278.62 61.38 335.50
front_transition_45 61.0 335.5
fast_front_rect metal4 60.62 335.12 61.38 339.88
front_transition_45 61.0 339.5
fast_front_rect metal5 60.62 339.12 61.38 343.38
fast_front_rect metal5 60.62 342.62 68.38 343.38
fast_front_rect metal5 67.62 338.02 68.38 343.38
fast_front_rect metal5 74.55 281.0 75.45 284.0
front_via via4 75.0 275.5

save
gds write /work/lane_rx_frontend.gds
quit -noprompt
