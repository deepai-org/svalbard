#!/usr/bin/env python3
"""PD21 low-C HS pad: per-leg front-end block `pt_hs_leg` (convkit rows, Magic DRC/LVS, KLayout via flow.export_gds).

Ports PAD RX VBIAS TERM_VCM TERM_ENABLE TERM_TRIM0..3 VDD VSS. One leg (the composition mirrors it for N):
  row0  25 x nfet_06v0 TU_i -> TERM_VCM: 10 base units 20/0.7 (gate TERM_ENABLE), 15 trim units 12/0.7
        (gates TERM_TRIMk, 1/2/4/8 units)
  row1  25 x ppolyf_u PAD -> TU_i: base 2 x 3.05 um, trim 2 x 2.0 um
  row2  AC coupling MIM 2 x 35 x 35 um (cap_mim_2f0_m4m5, ~4.9 pF): bottom plate = PAD, top = RX
  row3  RX bias ppolyf_u_1k 1 x 40 um (~40 kohm, HPF ~0.8 MHz) RX -> VBIAS; RX secondary clamps (drain diodes of
        grounded-gate 6 V devices): pfet_06v0 4/0.55 to VDD, nfet_06v0 4/0.7 to VSS
Every pad-reachable node is on 6 V devices (TU follows the pad during HBM); the RX side is DC-isolated by the MIM.
    python3 hs_leg_layout.py <work dir> [--legacy]

Default build = R-fixed leg (PC-14, 2026-11-14; resistances from analog/pads netres.py, which Magic's C-only extraction hides):
  TERM_VCM  Metal4 bus over the switch row (5 Metal1..Metal4 stacks on every source, via3 rows on the Metal3 rail), a 16 um
            Metal5 crossing over the resistor row and a 30 um Metal4+Metal5 strap up the free area right of the MIMs to the leg
            top (hs_pad_compose joins the two legs there with a wide Metal4 trunk).  The 1 um trunk in the bank stays (port).
  PAD       Metal4 strap over the Metal3 PAD rail, joined to the PAD trunk and to both MIM bottom plates, via3 rows, 3 via2
            per resistor head, and a Metal4/Metal5 landing pad with a via4 array for the composer's Metal5 feed.
  TU units  Metal2 + 5 via1 over every switch drain strap, second via1 on both resistor heads, second via2 at the Metal3
            track ends where Metal2 is free (each unit had 4 single cuts in series between switch and resistor).
  units     poly lengths 2.6 um (base) / 1.0 um (trim) instead of 3.05 / 2.0: about 9 ohm per leg of pad-side metal
            (mostly the protection shell) is in series with the units, so the trim range had to move down.
--legacy reproduces the published PD21 leg (1 um Metal3 rail, single Via2 per unit, one Via3; units 3.05 / 2.0 um).
"""
import json, shutil, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
CONV = HERE.parent / 'converters'
sys.path.insert(0, str(CONV / 'lib')); sys.path.insert(0, str(CONV))
import convkit as ck  # noqa: E402
from convkit import Mos, Res, Cap, Circuit  # noqa: E402

N_BASE = 10
GATES = ['TERM_ENABLE'] * N_BASE + [f'TERM_TRIM{k}' for k in range(4) for _ in range(1 << k)]

_mag = ck.mag_rects
def _mag_mv(path):
    r, props = _mag(path)
    for a, b in (('mvndiffc', 'ndiffc'), ('mvpdiffc', 'pdiffc')):
        if a in r and b not in r:
            r[b] = r[a]
    return r, props
ck.mag_rects = _mag_mv
_gen = ck.gencell_cmd
def _gen6(key):
    if key[0] == 'mos' and key[1] in ('nfet_06v0', 'pfet_06v0'):
        return (f'magic::gencell_makecell gf180mcu::{key[1]} w {key[2]} l {key[3]} nf 1 guard 1 topc 0 botc 1 '
                'full_metal 1 gate_to_polycont 0.6 gate_extension 0.8')
    if key[0] == 'resu':
        return f'magic::gencell_makecell gf180mcu::ppolyf_u w {key[1]} l {key[2]} guard 1 full_metal 1'
    return _gen(key)
ck.gencell_cmd = _gen6
_pg = ck.pcell_geometry
def _pg_u(key, path):
    return _pg(('res',) + tuple(key[1:]) if key[0] == 'resu' else key, path)
ck.pcell_geometry = _pg_u


class ResU(Res):
    """Unsalicided low-R p-poly (ppolyf_u) unit, same pins as convkit Res."""
    def spice(self):
        return [f'X{self.name}_{i} {self.a} {self.b} {self.sub} ppolyf_u r_width={self.w}u r_length={self.l}u' for i in range(self.m)]
    def key(self):
        return ('resu', self.w, self.l)


def circuit(name='pt_hs_leg', lb=2.6, lt=1.0):
    d = []
    for i, g in enumerate(GATES):
        # base units (always on when terminated): 20 um switch, 2 x 3.05 um poly; trim units (often off): 12 um
        # switch (off-state C 12.8 vs 21 fF) with 2 x 2.0 um poly, same unit resistance within the corner spread
        ws, lu = (20., lb) if g == 'TERM_ENABLE' else (12., lt)
        d.append(Mos(f'S{i}', 'nfet_06v0', ws, .7, f'TU{i}', g, 'TERM_VCM', 'VSS'))
        d.append(ResU(f'R{i}', 2., lu, 'PAD', f'TU{i}', 'VSS'))
    d.append(Cap('CAC', 35., 35., 'RX', 'PAD', m=2))
    d.append(Res('RB', 1., 40., 'VBIAS', 'RX', 'VSS'))
    d.append(Mos('CLH', 'pfet_06v0', 4., .55, 'RX', 'VDD', 'VDD', 'VDD', flip=True))
    d.append(Mos('CLL', 'nfet_06v0', 4., .7, 'RX', 'VSS', 'VSS', 'VSS', flip=True))
    # Protection-rail precharge (C of the pad->rail diodes at low CM): drain diode VDD (p+) -> RAILPRE (n-well),
    # routed to the shell's ATB_ESD_RAIL tap (480 kohm to the rail). Reverse-biased when unpowered (no backfeed).
    d.append(Mos('PRE', 'pfet_06v0', 4., .55, 'VDD', 'RAILPRE', 'RAILPRE', 'RAILPRE'))
    rows = [[f'S{i}' for i in range(len(GATES))], [f'R{i}' for i in range(len(GATES))], ['CAC'], ['RB', 'CLH', 'CLL', 'PRE']]
    ports = ['PAD', 'RX', 'VBIAS', 'TERM_VCM', 'TERM_ENABLE', 'TERM_TRIM0', 'TERM_TRIM1', 'TERM_TRIM2', 'TERM_TRIM3', 'VDD', 'VSS', 'RAILPRE']
    c = Circuit(name, ports, d, rows=rows, wide_nets={'PAD': 2.0, 'VSS': 2.0, 'TERM_VCM': 1.0, 'RX': 1.0})
    c.notes = ['pt_hs_leg (PD21): termination units + AC-coupling MIM + RX bias/clamps, one leg']
    return c


def r_fix(L):
    """Low-resistance overlays (see the module docstring). Painted after the convkit build; same nets, no new devices."""
    m3 = lambda net: max((s for s in L.shapes if s[0] == 'metal3' and s[5] == net), key=lambda s: (s[3] - s[1]) * (s[4] - s[2]))
    _, vx1, vy1, vx2, vy2, _ = m3('TERM_VCM'); _, px1, py1, px2, py2, _ = m3('PAD')
    top, right = L.bbox[3], L.bbox[2]
    xs2 = right - 2.; xc1 = xs2 - 16.; xs1 = xs2 - 30.      # strap right edge, Metal5 crossing left edge, upper strap left edge
    sw = [u for u in L.rows[0]['units']]
    if xs1 < max(u['ox'] + u['box'][2] for r in L.rows[2:] for u in r['units']) + 5.: raise ValueError('no free column for the TERM_VCM strap')
    # --- TERM_VCM
    L.net = 'TERM_VCM'
    src = [(u['ox'] + u['view']['S'][0]['x'], u['oy'] + u['view']['S'][0]['y']) for u in sw]
    yb1 = min(y for _, y in src) - 2.5 - 4 * 2. - .45; yb2 = vy2 + .16
    L.rect('metal4', .5, yb1, xs2, yb2)                                      # bus over the switch row and the Metal3 rail
    for x, y in src:
        for k in range(5): L.via(x, ck.q(y - 2.5 - 2. * k), 1, 4)            # source Metal1 strap -> bus
    L.rect('via3', .6, vy1 + .11, vx2 - .3, vy2 - .11)                       # rail -> bus, 2 rows of cuts
    ys1 = py2 + 3.                                                           # upper strap starts above the PAD rail
    L.rect('metal5', xc1, yb1 + .5, xs2, ys1 + 6.)                           # crossing over the TU tracks / resistor row / PAD rail
    L.rect('via4', xc1 + .5, yb1 + 1., xs2 - .5, vy2 - .3)
    L.rect('metal4', xs1, ys1, xs2, top); L.rect('metal5', xs1, ys1, xs2, top)
    y = ys1 + .5
    while y + 2. < top - .5:
        L.rect('via4', xs1 + .5, y, xs2 - .5, y + 2.); y += 8.
    # --- PAD
    L.net = 'PAD'
    xt = L.trunk_x['PAD']; xp2 = xc1 - 3.; ty = (py1 + py2) / 2
    L.rect('metal4', xt - 1., py1, xp2, py2 + .25)                           # strap over the rail, from the trunk
    L.rect('via3', xt - .8, py1 + .23, xp2 - .3, py2 - .23)                  # 3 rows of cuts
    for u in L.rows[2]['units']:
        if isinstance(u['dev'], Cap):
            p = L.geom[u['dev'].key()]['plate']
            L.rect('metal4', u['ox'] + p[0] + .2, py2, u['ox'] + p[2] - .2, u['oy'] + p[1] + .2)   # strap -> MIM bottom plate
    L.rect('metal4', xt - 2., py1 - 2., xt + 2., py2 + 2.); L.rect('metal5', xt - 2., py1 - 2., xt + 2., py2 + 2.)
    L.rect('via4', xt - 1.7, py1 - 1.7, xt + 1.7, py2 + 1.7)                 # landing of the composer's Metal5 feed
    for u in L.rows[1]['units']:
        x = ck.q(u['ox'] + u['view']['A'][0]['x']); y = ck.q(u['oy'] + u['view']['A'][0]['y'])
        if u['pins']['A'] != 'PAD': raise ValueError('resistor head A is not PAD')
        L.rect('metal2', x - .2, ty, x + .2, ty + .8)
        for dy in (-.6, .6): L.via(x, ck.q(ty + dy), 2, 3)
        L.rect('metal2', x - .2, y - .2, x + .8, y + .2); L.via(ck.q(x + .6), y, 1, 2)       # second via1 on the head
        L.rect('metal1', x - .19, y - .19, x + .79, y + .19)                                  # (no Metal1 notch between the two pads)
    # --- TU units (switch drain -> Metal3 track -> resistor head): every unit had 4 single cuts in series
    other = lambda net: [s for s in L.shapes if s[0] == 'metal2' and s[5] != net]
    added = 0
    for us, ur in zip(sw, L.rows[1]['units']):
        net = us['pins']['D']
        if ur['pins']['B'] != net: raise ValueError('unit order')
        L.net = net
        xd = ck.q(us['ox'] + us['view']['D'][0]['x']); yd = ck.q(us['oy'] + us['view']['D'][0]['y'])
        L.rect('metal2', xd - .2, yd - 10.7, xd + .2, yd)                                     # Metal2 over the drain strap
        for k in range(5): L.via(xd, ck.q(yd - 2.5 - 2. * k), 1, 2)
        xb = ck.q(ur['ox'] + ur['view']['B'][0]['x']); yb = ck.q(ur['oy'] + ur['view']['B'][0]['y'])
        L.rect('metal2', xb - .8, yb - .2, xb + .2, yb + .2); L.via(ck.q(xb - .6), yb, 1, 2)  # second via1 on the head
        L.rect('metal1', xb - .79, yb - .19, xb + .19, yb + .19)
        _, tx1, ty1, tx2, ty2, _ = m3(net); tyc = ck.q((ty1 + ty2) / 2); d = 1 if xb > xd else -1
        if abs(xb - xd) >= 2.6:                                                               # second via2 at both track ends where Metal2 is free
            for x0, dd in ((xd, d), (xb, -d)):
                bx = (min(x0, x0 + .6 * dd) - .2, tyc - .2, max(x0, x0 + .6 * dd) + .2, tyc + .2)
                if any(bx[0] - .3 < o[3] and o[1] < bx[2] + .3 and bx[1] - .3 < o[4] and o[2] < bx[3] + .3 for o in other(net)): continue
                L.rect('metal2', *bx); L.via(ck.q(x0 + .6 * dd), tyc, 2, 3); added += 1
    L.net = None
    return dict(tu_extra_via2=added, vcm_strap=[xs1, xs2], vcm_crossing=[xc1, xs2], vcm_bus=[.5, yb1, xs2, yb2], pad_strap=[xt - 1., py1, xp2, py2 + .25], pad_landing=[xt - 2., py1 - 2., xt + 2., py2 + 2.])


def layout(work, legacy=False):
    import flow
    c = circuit(lb=3.05, lt=2.0) if legacy else circuit()
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    sch = c.spice(include_macros=False)
    (work / f'{c.name}.sch.spice').write_text(sch)
    L = ck.Layout(c, work).build()
    fix = None if legacy else r_fix(L)
    L.write()
    (work / f'{c.name}.lvs_sch.spice').write_text(L.lvs_reference(sch))
    res = ck.lvs(work, f'{c.name}.lvs.spice', c.name, f'{c.name}.lvs_sch.spice', c.name)
    gx = flow.export_gds(work, c)
    info = dict(L.report, lvs=res['final'], lvs_unique=res['match_unique'], gds_export=gx, r_fix=fix)
    (work / 'layout-info.json').write_text(json.dumps(info, indent=2, default=str) + '\n')
    print(json.dumps({k: info.get(k) for k in ('drc_count', 'lvs', 'lvs_unique')}, default=str), gx.get('klayout_drc'))
    return info


if __name__ == '__main__':
    layout(Path(sys.argv[1]).resolve(), legacy='--legacy' in sys.argv[2:])
