#!/usr/bin/env python3
"""pad_wirepad b7 -> b7v: wide TERM_VCM exit on the top edge (2026-11-24, review-b7 C3; coordinator: EM sign-off at 85 C).

    python3 usb_vcm_pin.py <b7 combined.gds> <out.gds>          (KLayout python, inside the pad image)

b7's TERM_VCM leaves the cell through a 2.35 um Metal4 neck at x 118.4-120.75 (y 1432.6-1434.72, between the TERM_TRIM2 and VDD
pins): 1.97 x the 85 C rating while HS is active (scratch/pads-core/esdopt/usb/bench/b7-hs-em.json). TERM_VCM's own Metal3 / Metal4
plate (x 118.4-313, y 1345-1432.6) ends 2.12 um below the edge, and the edge strip above it is free from x 190.5 (VSS pin end) to 313.
This adds Metal4 x 195-310, y 1432.6-1434.72 (merging with the plate, 4.5 um from the VSS pin) and a second TERM_VCM pin there.
The old 0.44 um pin (x 118.78-119.22) loses its pin shape and label, so the router lands on the wide pin; its metal stays.
Also (Magic MIMTM.2, 9 errors in b7, would fail the shuttle precheck's Magic run): the three Via4 cuts from the TERM_GATE /
mim-feed Metal5 risers onto 0.4 um Metal4 lines (centres (81, 672.9), (87, 932.9), (88, 1010.9)) get a Metal4 landing of cut + 0.4 um.
No device or netlist change.
"""
import sys
import klayout.db as k

X0, X1, Y0, YT = 195.0, 310.0, 1432.6, 1434.72


def main(src, dst):
    L = k.Layout(); L.read(src); top = L.top_cell()
    m4, pin = L.layer(46, 0), L.layer(46, 10)
    clash = k.Region(top.begin_shapes_rec_touching(m4, k.DBox(X0 - 4., Y0 + .01, X1 + 4., YT).to_itype(L.dbu))) & \
        k.Region(k.DBox(X0 - .5, Y0 + .01, X1 + .5, YT).to_itype(L.dbu))
    done = not clash.is_empty()      # idempotent: re-running on its own output only adds what is missing
    if done: assert (clash - k.Region(k.DBox(X0, Y0, X1, YT).to_itype(L.dbu))).is_empty(), f'foreign Metal4 in the pin strip: {clash}'
    old = k.DBox(118.5, 1432.9, 119.5, YT)
    for li in (pin, m4):
        for sh in [x for x in top.shapes(li).each_touching(old) if (x.is_text() and x.text_string == 'TERM_VCM') or (li == pin and not x.is_text())]:
            top.shapes(li).erase(sh)
    if not done: top.shapes(m4).insert(k.DBox(X0, Y0, X1, YT))
    for cx, cy in ((81.0, 672.9), (87.0, 932.9), (88.0, 1010.9)):    # MIMTM.2 landings
        top.shapes(m4).insert(k.DBox(cx - .53, cy - .53, cx + .53, cy + .53))
    if not done:
        top.shapes(pin).insert(k.DBox(X0, YT - .5, X1, YT))
        for li in (m4, pin): top.shapes(li).insert(k.DText('TERM_VCM', k.DTrans((X0 + X1) / 2, YT - .25)))
    L.write(dst)
    print('TERM_VCM pin added', (X0, Y0, X1, YT))


if __name__ == '__main__':
    main(*sys.argv[1:3])
