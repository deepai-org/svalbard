#!/usr/bin/env python3
"""pad_rftxpad t2 -> t3: local positive ESD path (2026-11-24; diagnosis in scratch/pads-core/esdopt/rf/STATUS.md).

    python3 rftx_band.py <t2.gds> <out.gds>          (KLayout python, inside the pad image)

Why: t2 has only down-diodes at the pad sites (RF_TX swings ~0.8 V above the supply, so no up-diode to the supply, PC-31).
Positive zaps went through the shell's core network (62 ohm to its diodes, 34 ohm to ESD_RAIL, 51 ohm from the clamp's VSS
to the site) and the site down-diodes avalanched at 9 mA/um (CDM 2 A).  t3 adds, in the free band at depth 352-389 between
the ring (ends at 350) and the shell (starts at 396):
  * per leg 10 pd2nw up-diodes PAD -> ESD_RAIL (not the supply) and 4 nd2ps down-diodes VSS -> PAD (P+N return);
  * Metal5 ESD_RAIL plane over the band + strap x 145-205 up to the shell's ESD_RAIL Metal3 band (745-768.7, the rail clamp's drains);
  * Metal5 VSS strap x 210-265 from depth 343 (overlapping the ring's innermost DVSS band 342-348.39 on Metal5, same net, no via)
    up to the clamp's VSS Metal3 band (770.7-799.9), with Via4 onto the shell's VSS Metal4 tie bar (396-404) on the way;
  * a second PAD Metal2 path parallel to each neck: x 50.5-73 (P) / 261.5-284 (N) from depth 101.5 to the band.
Shell, sites, pins and outline unchanged.  Finger pattern = pad_site_primary.py up / down rows (25 um fingers, pitch 6).
"""
import sys
import klayout.db as k

sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads')
import pad_site_primary as sp

M = {1: 34, 2: 36, 3: 42, 4: 46, 5: 81}; V = {1: 35, 2: 38, 3: 40, 4: 41}
YC = 370.0                                  # finger row centre (fingers 355.66-384.34)
PB = (YC - 7.5, YC - .5)                    # PAD bar (Via1 on the centre stripe, 7 per finger)
SB = (YC + .5, YC + 5.4)                    # up rows: substrate-tap bar;   down rows: VSS bar runs SB[0]..KB[1]
KB = (YC + 5.8, YC + 14.6)                  # up rows: n-well (cathode) bar
# leg: neck (x1, x2), down-finger centres, up-finger centres, PAD Metal3 row x range, parallel strip x range
OPT = dict(n_up=10, n_dn=4, strip=True, pad_m4=True, esd_y0=356.)   # esd_y0: ESD Metal5 plane bottom (376 = over the n-well bars only)


def legs(o):
    nu, nd_ = int(o['n_up']), int(o['n_dn'])
    return {'P': dict(neck=(25.5, 49.5), dn=[54. + 6 * i for i in range(nd_)], up=[54. + 6 * nd_ + 3. + 6 * i for i in range(nu)], strip=(51., 73.)),
            'N': dict(neck=(236.5, 260.5), dn=[265. + 6 * i for i in range(nd_)], up=[141. + 6 * i for i in range(nu)], strip=(262., 284.))}
ESD_PLANE = (15., 356., 205., 385.5)      # < 30 um tall (MSLOT5.1)
ESD_STRAP = ((145., 173.), (177., 205.))   # two columns < 30 um wide
ESD_BAND = (745.5, 768.2)                   # shell ESD_RAIL Metal3 band (7.17-300.3, 745.24-768.74)
VSS_STRAP = ((210., 236.), (239., 265.))
VSS_BAND = (771.2, 799.4)                   # shell VSS Metal3 band (7.17-300.3, 770.74-799.87)
VSS_BAR4 = (396.5, 403.5)                   # shell VSS Metal4 tie bar (6-225, 396-404)


def main(src, dst, optjson='{}'):
    import json
    o = dict(OPT); o.update(json.loads(optjson)); LEGS = legs(o)
    L = k.Layout(); L.read(src); top = L.cell('pad_rftxpad')
    sp.load_primitives(L)
    nd, pd = L.cell(sp.ND), L.cell(sp.PD)
    cnt = {}

    def box(layer, x1, y1, x2, y2):
        top.shapes(L.layer(layer, 0)).insert(k.DBox(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))

    def via1(x, y):
        box(M[1], x - .19, y - .19, x + .19, y + .19); box(V[1], x - .13, y - .13, x + .13, y + .13); box(M[2], x - .2, y - .2, x + .2, y + .2)
        cnt['via1'] = cnt.get('via1', 0) + 1

    def varray(v, x1, y1, x2, y2, pitch=.7):
        nx = int((x2 - x1 - .4 - .26) / pitch) + 1; ny = int((y2 - y1 - .4 - .26) / pitch) + 1
        assert nx >= 1 and ny >= 1, (v, x1, y1, x2, y2)
        ax = (x1 + x2) / 2 - (nx - 1) * pitch / 2; ay = (y1 + y2) / 2 - (ny - 1) * pitch / 2
        for i in range(nx):
            for j in range(ny):
                cx, cy = ax + i * pitch, ay + j * pitch; box(V[v], cx - .13, cy - .13, cx + .13, cy + .13)
        cnt[f'via{v}'] = cnt.get(f'via{v}', 0) + nx * ny

    def stack(v_from, v_to, x1, y1, x2, y2):   # metal v_from+1 .. v_to+1 plates with via arrays v_from..v_to
        for v in range(v_from, v_to + 1):
            box(M[v + 1], x1, y1, x2, y2); varray(v, x1, y1, x2, y2)

    for leg, g in LEGS.items():
        dn, up, (n1, n2) = g['dn'], g['up'], g['neck']
        for x in dn:                                            # nd2ps: centre n+ = PAD, p+ ring = VSS
            top.insert(k.DCellInstArray(nd.cell_index(), k.DTrans(x, YC)))
            for dy in range(1, 8): via1(x, YC - dy)
            for dy in range(1, 12):
                for s in (-1.03, 1.03): via1(x + s, YC + dy)
        for x in up:                                            # pd2nw: centre p+ = PAD, n-well ring = ESD_RAIL, outer p+ = VSS
            top.insert(k.DCellInstArray(pd.cell_index(), k.DTrans(x, YC)))
            for dy in range(1, 8): via1(x, YC - dy)
            for s in (-1., 1.):
                for dy in range(1, 6): via1(x + s * 1.87, YC + dy)
                for dy in range(6, 12): via1(x + s * .99, YC + dy)
        dl, dr = min(dn) - 2., max(dn) + 2.; ul, ur = min(up) - 2.3, max(up) + 2.3
        lo, hi = min(dl, ul), max(dr, ur)
        # Metal2 bars, one set per group (the N leg's groups sit either side of its neck and VSS strip)
        for a, b in ((dl, dr), (ul, ur)): box(M[2], a, PB[0], b, PB[1]); varray(2, a + .2, PB[0] + .2, b - .2, PB[1] - .2)
        box(M[2], dl, SB[0], dr, KB[1])                         # down group VSS bar
        box(M[2], ul, SB[0], ur, SB[1])                         # up group substrate-tap bar
        box(M[2], ul, KB[0], ur, KB[1])                         # up group n-well bar (ESD_RAIL)
        # PAD: Metal3 + Metal4 row over both groups and the neck (Via2 onto the neck Metal2); crosses the VSS strip on Metal3/4 only
        px1, px2 = min(lo, n1 + 1.), max(hi, n2 - 1.)
        varray(2, n1 + 1.2, PB[0] + .2, n2 - 1.2, PB[1] - .2)
        box(M[3], px1, PB[0] + .2, px2, PB[1] - .2)
        if o['pad_m4']: box(M[4], px1, PB[0] + .2, px2, PB[1] - .2); varray(3, px1 + .2, PB[0] + .4, px2 - .2, PB[1] - .4)
        # parallel PAD path from the site: Metal2 strip joined to the neck along its length, up to the down group's PAD bar
        #   (a separate strip 1.5 um from the neck, bridged every ~80 um: no merged Metal2 wider than 30 um, MSLOT2.1)
        if o['strip']:
            s1, s2 = g['strip']; box(M[2], s1, 101.5, s2, PB[0] + .1)
            for yb in (101.5, 180., 260., 340.): box(M[2], n2 - .5, yb, s1 + .5, yb + 8.)
        # ESD_RAIL: n-well bar -> Metal3 -> Metal4 -> Metal5 plane
        stack(2, 4, ul + .2, KB[0] + .2, ur - .2, KB[1] - .2)
        # VSS: down VSS bar + up substrate bar -> Metal3 row (SB) -> to the VSS strap
        varray(2, dl + .2, SB[0] + .2, dr - .2, KB[1] - .2); varray(2, ul + .2, SB[0] + .2, ur - .2, SB[1] - .2)
        box(M[3], dl + .2, SB[0] + .2, dr - .2, KB[1] - .2)
    # VSS Metal3 row across the band at SB (joins every substrate / VSS bar), landed on the VSS strap at x 255-264
    pl, pr = LEGS['P'], LEGS['N']
    box(M[3], min(pl['dn']) - 1.8, SB[0] + .2, 264., SB[1] - .2)
    box(M[3], 255., SB[0] + .2, max(pr['dn']) + 1.3, SB[1] - .2)
    stack(3, 4, 255., SB[0] + .2, 264., SB[1] - .2)
    # Metal5 ESD_RAIL plane + strap to the shell ESD_RAIL band
    box(M[5], ESD_PLANE[0], o['esd_y0'], ESD_PLANE[2], ESD_PLANE[3])
    for a, b in ESD_STRAP:
        box(M[5], a, o['esd_y0'], b, ESD_BAND[1]); box(M[4], a + .5, ESD_BAND[0], b - .5, ESD_BAND[1])
        varray(3, a + .7, ESD_BAND[0] + .2, b - .7, ESD_BAND[1] - .2); varray(4, a + .7, ESD_BAND[0] + .2, b - .7, ESD_BAND[1] - .2)
    # Metal5 VSS strap: ring DVSS overlap (343-348.39, Metal5 only) -> shell VSS Metal4 bar -> shell VSS Metal3 band
    for a, b in VSS_STRAP:
        box(M[5], a, 343., b, VSS_BAND[1]); box(M[4], a + .5, VSS_BAND[0], b - .5, VSS_BAND[1])
        varray(3, a + .7, VSS_BAND[0] + .2, b - .7, VSS_BAND[1] - .2); varray(4, a + .7, VSS_BAND[0] + .2, b - .7, VSS_BAND[1] - .2)
    varray(4, VSS_STRAP[0][0] + .2, VSS_BAR4[0] + .2, 224.5, VSS_BAR4[1] - .2)
    L.write(dst, k.SaveLayoutOptions())
    print('band:', o, cnt)


if __name__ == '__main__':
    main(*sys.argv[1:4])
