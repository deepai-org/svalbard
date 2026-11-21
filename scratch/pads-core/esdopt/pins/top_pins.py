#!/usr/bin/env python3
"""ASM-2 pin-move variants of published pad cells (no device / netlist change).

    python3 top_pins.py <family> <published.gds> <out.gds>        (KLayout python, e.g. inside the pad image)
    family: rf_pair | rftxpad | single_leg | hspad

Reads the published GDS, adds same-net Metal3/Metal4/Metal5 routing in the top cell from each core-side port to the
top (core-facing) edge (max y, flush with the bbox), puts the port label there on a Metal4 pin, and deletes the old
inner / side label of that port. PAD_P / PAD_N (already Metal5 pins on the top edge), DVDD (ring landing) and the
internal ESD_RAIL label are not touched. Bond openings, devices and every existing shape stay where they are.

Why a post-processor and not a generator option: the rf_pair / rftxpad / single_leg generator (protection_pad_ss.py)
cannot rebuild the published cells any more (its network input scratch/pads-pd12/v2/macro was deleted, and the
published GDS was renamed / prefixed after it); hs_pad_compose.py imports pad_site_primary.py, which changed since a6
(5ff82d2a -> 4a3b087f) and is being edited. The post-processor works on the exact published geometry instead.
"""
import sys
import klayout.db as k

M = {3: 42, 4: 46, 5: 81}
V = {3: 40, 4: 41}

# rf shell (rf_pair / rftxpad / single_leg; identical left half). Free space checked on the published GDS:
#  ATB_ESD_RAIL: Metal3 tip (91.18-91.98, 438-442) -> Metal3 y 436.2-436.8 west (nothing on Metal3 at x 0-100,
#    y 396-444 except the tip) -> via3 at x 2 -> Metal4 x 1-3 up to the top (Metal4 column x -0.06..5.82 is free
#    from y 444 to the top; below 444 the nearest Metal4 is the return route at x >= 6).
#  VSS: the network's Metal3 VSS band (x 7.2-300.3, y 770.7-799.9) -> Metal3 x 8-18 up to the top (Metal3 free above
#    800 for x < 262) -> via3 array -> Metal4 pin x 8-18 (Metal4 free above 800 for x < 58.8; Metal5 ESD_RAIL starts at x 20).
RF = dict(remove=['VSS', 'ATB_ESD_RAIL', 'PAD_P', 'PAD_N'],      # the inner Metal3 labels; PAD_P / PAD_N keep their top Metal5 pins
          remove_layers=[42])

# hspad: the eleven channel straps (Metal5, y 598.75-630.25, x trunk..492) are tapped in the free column x 417-461,
# Metal4 risers in the channel (no Metal4 at x 340-461 between the legs) up to y 633.5, Metal5 risers above (column
# x 416.5-461 is free on Metal5 from y 632 to the top, everything is free above y 817.5), Metal4 pins at the top edge.
HS_NETS = [  # name, strap y, riser width
    ('TERM_TRIM0', 598.75, 1.), ('TERM_TRIM1', 601.25, 1.), ('TERM_TRIM2', 603.75, 1.), ('TERM_TRIM3', 606.25, 1.),
    ('VSS', 608.75, 3.), ('RX_P', 612.75, .6), ('RX_N', 618.75, .6), ('VDD', 622.75, 3.), ('TERM_ENABLE', 625.25, 1.),
    ('TERM_VCM', 627.75, 3.), ('VBIAS', 630.25, 1.)]


def main(family, src, dst):
    L = k.Layout(); L.read(src); top = L.top_cell(); dbu = L.dbu
    bb = top.dbbox(); ytop = bb.top

    def box(m, x1, y1, x2, y2):
        top.shapes(L.layer(m, 0)).insert(k.DBox(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))

    def cuts(v, x1, y1, x2, y2, pitch=.6):
        """via cuts (0.26) on a grid inside the box, >= 0.12 from its edges (the generators' stack() pattern)."""
        nx = max(1, int((x2 - x1 - .24 - .26) / pitch + 1e-9) + 1); ny = max(1, int((y2 - y1 - .24 - .26) / pitch + 1e-9) + 1)
        if nx * ny > 9: pitch = max(pitch, .62)
        x0 = (x1 + x2) / 2 - (nx - 1) * pitch / 2; y0 = (y1 + y2) / 2 - (ny - 1) * pitch / 2
        for i in range(nx):
            for j in range(ny):
                cx, cy = x0 + i * pitch, y0 + j * pitch
                box(V[v], cx - .13, cy - .13, cx + .13, cy + .13)

    def label(name, m, x, y):
        top.shapes(L.layer(M[m], 10)).insert(k.DText(name, k.DTrans(x, y)))

    def drop_labels(names, layers):
        n = 0
        for ln in layers:
            li = L.find_layer(ln, 10)
            if li is None: continue
            for s in list(top.shapes(li).each()):
                if s.is_text() and s.text.string in names: s.delete(); n += 1
        return n

    pins = []
    if family in ('rf_pair', 'rftxpad', 'single_leg'):
        names = [n for n in RF['remove'] if not (family == 'single_leg' and n == 'PAD_N')]
        n = drop_labels(names, RF['remove_layers'])
        if n != len(names): raise SystemExit(f'expected {len(names)} inner labels, removed {n}')
        # ATB_ESD_RAIL
        box(M[3], 91.28, 436.2, 91.88, 438.6)             # down from the tip
        box(M[3], 1.6, 436.2, 91.88, 436.8)               # west, 0.6 um
        box(M[3], 1.4, 436.0, 2.6, 437.0); cuts(3, 1.4, 436.0, 2.6, 437.0)
        box(M[4], 1.0, 435.9, 3.0, ytop)                  # riser = pin column
        label('ATB_ESD_RAIL', 4, 2.0, ytop - .5); pins.append(('ATB_ESD_RAIL', 'Metal4', 1.0, 3.0))
        # VSS
        box(M[3], 8.0, 790.0, 18.0, ytop)
        box(M[4], 8.0, 903.0, 18.0, ytop); cuts(3, 8.0, 903.0, 18.0, 911.0, pitch=.7)
        label('VSS', 4, 13.0, ytop - .5); pins.append(('VSS', 'Metal4', 8.0, 18.0))
        for nm, x1, x2 in (('PAD_P', 286., 290.), ('PAD_N', 302., 306.)):
            if family == 'single_leg' and nm == 'PAD_N': continue
            pins.append((nm, 'Metal5 (published, unchanged)', x1, x2))
    elif family == 'hspad':
        names = [n for n, _, _ in HS_NETS]
        n = drop_labels(names, [81])
        if n != len(names): raise SystemExit(f'expected {len(names)} side labels, removed {n}')
        x, GAP, RXGAP, YC = 418.0, 1.6, 4.5, 633.5   # RX_P / RX_N: 0.6 um risers, 4.5 um clear on both sides (C)
        for name, ys, w in HS_NETS:
            xc = x + w / 2; h = max(w / 2, .4)
            # tap on the strap: Metal5 pad + via4 cuts + Metal4 pad
            # (0.8 um tall: keeps the pad inside the strap pitch; one row of cuts)
            box(M[5], xc - h, ys - .4, xc + h, ys + .4); box(M[4], xc - h, ys - .4, xc + h, ys + .4); cuts(4, xc - h, ys - .4, xc + h, ys + .4)
            box(M[4], xc - w / 2, ys - .4, xc + w / 2, YC + h)                    # Metal4 riser through the channel
            box(M[4], xc - h, YC - h, xc + h, YC + h); box(M[5], xc - h, YC - h, xc + h, YC + h); cuts(4, xc - h, YC - h, xc + h, YC + h)
            box(M[5], xc - w / 2, YC - h, xc + w / 2, ytop)                       # Metal5 riser to the top edge
            box(M[4], xc - w / 2, ytop - 6., xc + w / 2, ytop); cuts(4, xc - w / 2, ytop - 6., xc + w / 2, ytop - 1.)
            label(name, 4, xc, ytop - .5); pins.append((name, 'Metal4', xc - w / 2, xc + w / 2))
            x += w + (RXGAP if name in ('VSS', 'RX_P', 'RX_N') else GAP)
        if x - GAP > 460.0: raise SystemExit('hspad riser column overflow')
    else:
        raise SystemExit('unknown family ' + family)
    L.write(dst)
    nb = top.dbbox()
    if (nb.left, nb.bottom, nb.right, nb.top) != (bb.left, bb.bottom, bb.right, bb.top): raise SystemExit(f'bbox changed {bb} -> {nb}')
    for p in pins: print(f'PIN {p[0]} {p[1]} x {p[2]:.3f}-{p[3]:.3f} top y {ytop}')


if __name__ == '__main__':
    main(*sys.argv[1:4])
