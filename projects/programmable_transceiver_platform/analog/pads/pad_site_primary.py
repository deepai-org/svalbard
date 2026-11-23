#!/usr/bin/env python3
"""Pad-site primary ESD diodes (PC-27, 2026-11-18): the `pad_tlp_flat` pattern as a reusable generator.

Primary steering diodes INSIDE the 75 um pad site, between the bond pad and the core, under the provider ring rail cell
(`5LM_METAL_RAIL`: Metal3-5 rails over depth 70-348.4, a p-tap frame on COMP / Metal1 at the site perimeter, nothing else).
Only COMP / Metal1 / Metal2 are used in the band, plus Via2 + Metal3 landing pads that lie INSIDE one rail band each and
tie the diode bars straight to the ring: down-diodes (diode_nd2ps_06v0, PAD -> ring DVSS) and up-diodes
(diode_pd2nw_06v0, PAD -> ring DVDD).  The family's Metal2 neck then carries signal current only.

Site-local coordinates (um): x 0..75 across the site, y = depth from the die edge (bond pad plate ends at 65.325).
All fingers sit RIGHT of the family's Metal2 neck, 25 um fingers at `pitch`, two rows:

    y_dn row (nd2ps):  PAD bar y_dn-pad_bar-0.5 .. y_dn-0.5 (pad_bar Via1 per finger on the centre stripe), merged with a Metal2
                       plate down to `plate_y` (overlaps the bond pad plate: fed over the whole plate width);
                       VSS bar y_dn+0.5 .. y_dn+18.5 (11 Via1 on BOTH sides of the p+ ring) with a Via2 / Metal3 landing
                       inside the DVSS band 70-117.
    y_up row (pd2nw):  PAD bar y_up-pad_bar-0.5 .. y_up-0.5 from the neck (neck widened to the left by `neck_extra_left`);
                       substrate-tap bar y_up+0.5 .. y_up+5.4 (5 Via1 per side, landing in DVSS 70-117, Metal2 strap
                       round the right end to the VSS bar); DVDD bar y_up+5.8 .. `y_vdd_top` (6 Via1 per side on the
                       n-well ring) with landings inside the DVDD bands 118-125 and 134-197.
    Metal1 bridge under the neck from the VSS bar to the family's own VSS Metal2 strip (`vss_strip`), so the cell-level
    netlist has ONE VSS without relying on the ring (set vss_strip=None to leave it out).

The two sites of a differential pad are joined on DVDD only by the ring (label `DVDD` on each site's Metal3 landing).

Use from a composer (KLayout python, inside the layout image):
    import pad_site_primary as sp
    sp.load_primitives(layout, prim_dir)                       # once; reads the two diode GDS, drops their texts
    info = sp.draw(layout, root_cell, x0, opt)                 # x0 = site origin; opt = dict(sp.OPT, neck=(..), ...)
    lines = sp.reference_lines('SP', 'PAD_P', 'VSS', 'DVDD', opt)   # devices for the LVS reference
    info['dvdd_label'] is where a `DVDD` text on Metal3 (42/10) belongs; info['shapes'] lists what was drawn.

Standalone (test cell `pad_site_primary`: plate stub + neck stub + VSS strip stub + the site; Magic DRC, extraction,
netgen LVS, read from the written GDS):
    python3 pad_site_primary.py --output-dir DIR [--n-dn 5 --n-up 5 --neck 33.5 41.5 --vss-strip 0.5 25.5 --opt-json '{...}']
"""
import argparse, json, shutil, subprocess, sys, hashlib
from pathlib import Path
HERE = Path(__file__).resolve().parent
PRIM = HERE / 'generated/protection-primitives'
ND, PD = 'diode_nd2ps_06v0', 'diode_pd2nw_06v0'
M = {1: 34, 2: 36, 3: 42, 4: 46, 5: 81}; V = {1: 35, 2: 38, 3: 40, 4: 41}

OPT = dict(
    neck=(33.5, 41.5),        # the family's Metal2 escape neck (x1, x2); fingers go right of it
    neck_extra_left=0.,       # neck widened to the left by this much from plate_y to the up-row PAD bar (0 = not):
                              # 6 um takes about 0.19 ohm off the up-diode path of an 8 um neck and costs about 22 fF
    pad_bar=7,                # PAD bar height in um = Via1 cuts per finger on the PAD side (1 um pitch); 2.3 fF per um and row
    vss_strip=(.5, 25.5),     # the family's VSS Metal2 strip to the ring stack (x1, x2), or None: no Metal1 bridge
    n_dn=5, n_up=5,           # fingers per row (25 um each); at pitch 6 and an 8 um neck at most 5 fit (x 46 .. 70)
    pitch=6., first_x=None,   # first finger centre; None = neck x2 + 4.5
    y_dn=82., y_up=113.5,     # row centres
    plate_y=62.,              # PAD plate starts here (overlaps the bond pad plate, which ends at 65.325)
    y_vdd_top=148.7,          # DVDD bar top
    dvss_band=(70., 117.), dvdd_bands=((118., 125.), (134., 197.)),   # ring Metal3 bands used for landings (5LM_METAL_RAIL)
    x_max=74.,                # nothing beyond this x (rail-cell p-tap frame from 74.6)
    n_up_left=0,              # (2026-11-20, pad_wirepad option A; 0 = the published pattern) extra pd2nw fingers in the up row LEFT of the
                              # neck (centres neck x1 - 4.5 - pitch*i): PAD bar from the neck, substrate-tap bar joined to `vss_strip` and
                              # landed on DVSS, own DVDD bar whose band-134 landing runs over the neck to the right DVDD bar (one DVDD net)
    n_dn_left=0,              # (2026-11-21, rf-shell option A; 0 = the published pattern) extra nd2ps fingers in the down row LEFT of the neck
                              # (centres neck x1 - 4.5 - pitch*i): PAD bar from the plate / neck, VSS bar joined to `vss_strip`, landed on DVSS
    no_up_row=False,          # (2026-11-21, pad_rftxpad option A; False = the published pattern) draw the down row only (needs n_up = 0)
)


def load_primitives(layout, prim_dir=PRIM):
    for n in (ND, PD):
        if layout.cell(n) is None:
            layout.read(str(Path(prim_dir) / f'{n}.gds'))
        c = layout.cell(n)
        for ix in layout.layer_indexes():
            for s in list(c.each_shape(ix)):
                if s.is_text(): s.delete()


def fingers(opt):
    f0 = opt['first_x'] if opt.get('first_x') is not None else opt['neck'][1] + 4.5
    n = max(opt['n_dn'], opt['n_up'])
    fx = [f0 + opt['pitch'] * i for i in range(n)]
    if fx[-1] + 4. > opt['x_max'] + 1e-9: raise ValueError(f'fingers do not fit: last centre {fx[-1]} + strap > x_max {opt["x_max"]}')
    return fx


def reference_lines(prefix, pad, vss, dvdd, opt):
    out = [f'D{prefix}N{i} {vss} {pad} {ND} pj=51.8u area=22.5p' for i in range(opt['n_dn'])]
    out += [f'D{prefix}P{i} {pad} {dvdd} {PD} pj=51.8u area=22.5p' for i in range(opt['n_up'])]
    out += [f'D{prefix}L{i} {pad} {dvdd} {PD} pj=51.8u area=22.5p' for i in range(int(opt.get('n_up_left', 0)))]
    out += [f'D{prefix}M{i} {vss} {pad} {ND} pj=51.8u area=22.5p' for i in range(int(opt.get('n_dn_left', 0)))]
    return out


def draw(layout, cell, x0, opt=OPT):
    """Draw one pad-site primary into `cell` at site origin x0.  Returns dict(dvdd_label, vss_label, pad_label, bbox, counts)."""
    import klayout.db as k
    o = dict(OPT); o.update(opt or {})
    fx = fingers(o); ndn, nup = o['n_dn'], o['n_up']
    yd, yu = o['y_dn'], o['y_up']
    n1, n2 = o['neck']; nl = n1 - o['neck_extra_left']
    cnt = dict(via1=0, via2=0)
    def box(layer, x1, y1, x2, y2):
        cell.shapes(layout.layer(layer, 0)).insert(k.DBox(x0 + min(x1, x2), min(y1, y2), x0 + max(x1, x2), max(y1, y2)))
    def via1(x, y):
        box(M[1], x - .19, y - .19, x + .19, y + .19); box(V[1], x - .13, y - .13, x + .13, y + .13); box(M[2], x - .2, y - .2, x + .2, y + .2); cnt['via1'] += 1
    def varray(v, x1, y1, x2, y2, pitch=.7):
        nx = int((x2 - x1 - .4 - .26) / pitch) + 1; ny = int((y2 - y1 - .4 - .26) / pitch) + 1
        if nx < 1 or ny < 1: raise ValueError(f'no room for a via array in {x1, y1, x2, y2}')
        ax = (x1 + x2) / 2 - (nx - 1) * pitch / 2; ay = (y1 + y2) / 2 - (ny - 1) * pitch / 2
        for i in range(nx):
            for j in range(ny):
                cx, cy = ax + i * pitch, ay + j * pitch
                box(V[v], cx - .13, cy - .13, cx + .13, cy + .13)
        cnt['via%d' % v] = cnt.get('via%d' % v, 0) + nx * ny
    def landing(x1, y1, x2, y2):          # Metal3 pad + Via2 array on a Metal2 bar
        box(M[3], x1, y1, x2, y2); varray(2, x1, y1, x2, y2)
    nb = int(o['pad_bar'])
    if not 3 <= nb <= 11: raise ValueError('pad_bar must be 3..11')
    if yu - nb - .5 < yd + 18.5 + .5 or yu - 14.34 < yd + 13.5 + 2.: raise ValueError('rows overlap')
    if yd + 18.3 > o['dvss_band'][1] - .2 or yd + .7 < o['dvss_band'][0] + .2: raise ValueError('VSS landing leaves the DVSS band')
    xl = fx[0] - 2.; xr = max(fx[:max(ndn, nup)]) + 1.5; xs = xr + 2.5        # bar left / right ends, strap right edge
    xr_dn, xr_up = fx[ndn - 1] + 1.5, fx[nup - 1] + 1.5
    if xs > o['x_max'] + 1e-9: raise ValueError('strap beyond x_max')
    if xl - n2 < .5: raise ValueError('first finger too close to the neck')
    nd, pd = layout.cell(ND), layout.cell(PD)
    if nd is None or pd is None: raise ValueError('call load_primitives(layout) first')
    # ---- down row: nd2ps, K (centre stripe) = PAD, A (p+ ring) = VSS
    for x in fx[:ndn]:
        cell.insert(k.DCellInstArray(nd.cell_index(), k.DTrans(x0 + x, yd)))
        for dy in range(1, nb + 1): via1(x, yd - dy)
        for dy in range(1, 12):
            for s in (-1.03, 1.03): via1(x + s, yd + dy)
    box(M[2], n2 - 1., o['plate_y'], xr_dn, yd - .5)                 # PAD plate + bar (fed from the bond pad plate below)
    box(M[2], xl, yd + .5, xs, yd + 18.5)                            # VSS bar (to the strap)
    landing(xl + .2, yd + .7, xr - .2, yd + 18.3)
    if o.get('no_up_row', False):         # (2026-11-21, pad_rftxpad option A; False = the published pattern) down row only: no up-diode,
        if nup or o.get('n_up_left', 0):   # no DVDD bar / landing / port (RF_TX swings above the supply, PC-31)
            raise ValueError('no_up_row needs n_up = 0 and n_up_left = 0')
        lab, yt = None, yd + 18.5
    else:
        # ---- up row: pd2nw, A (centre stripe) = PAD, K (n-well ring) = DVDD, outer p+ ring = VSS
        for x in fx[:nup]:
            cell.insert(k.DCellInstArray(pd.cell_index(), k.DTrans(x0 + x, yu)))
            for dy in range(1, nb + 1): via1(x, yu - dy)
            for s in (-1., 1.):
                for dy in range(1, 6): via1(x + s * 1.87, yu + dy)
                for dy in range(6, 12): via1(x + s * .99, yu + dy)
        box(M[2], nl, o['plate_y'], n2, yu - .5)                         # neck (drawn here too) + its widening
        box(M[2], n2 - 1., yu - nb - .5, xr_up, yu - .5)                    # PAD bar
        box(M[2], xl, yu + .5, xs, yu + 5.4)                             # substrate-tap bar
        ya, yb = max(yu + .7, o['dvss_band'][0] + .2), min(yu + 5.2, o['dvss_band'][1] - .2)
        if yb - ya >= .7: landing(xl + .2, ya, xr - .2, yb)
        box(M[2], xr + 1., yd + .5, xs, yu + 5.4)                        # VSS strap round the right end of the PAD bar
        yt = o['y_vdd_top']
        box(M[2], xl, yu + 5.8, xr_up, yt)                               # DVDD bar
        lab = None
        for b1, b2 in o['dvdd_bands']:
            ya, yb = max(yu + 6., b1 + .3), min(yt - .2, b2 - .3)
            if yb - ya >= .7:
                landing(xl + .2, ya, xr_up - .2, yb); lab = (x0 + (xl + xr_up) / 2, (ya + yb) / 2)
        if lab is None: raise ValueError('no DVDD landing: y_vdd_top / bands')
    # ---- optional up-row fingers left of the neck (n_up_left)
    nlu = int(o.get('n_up_left', 0))
    if nlu:
        vs = o.get('vss_strip')
        if not vs: raise ValueError('n_up_left needs vss_strip (the tap bar joins it)')
        fxl = [n1 - 4.5 - o['pitch'] * i for i in range(nlu)]
        xa, xb = min(fxl) - 1.5, max(fxl) + 2.
        if xa < vs[1] + 2.5: raise ValueError(f'n_up_left: fingers reach the VSS strip ({xa} < {vs[1] + 2.5})')
        for x in fxl:
            cell.insert(k.DCellInstArray(pd.cell_index(), k.DTrans(x0 + x, yu)))
            for dy in range(1, nb + 1): via1(x, yu - dy)
            for s_ in (-1., 1.):
                for dy in range(1, 6): via1(x + s_ * 1.87, yu + dy)
                for dy in range(6, 12): via1(x + s_ * .99, yu + dy)
        box(M[2], xa, yu - nb - .5, n1 + 1., yu - .5)                    # PAD bar from the neck
        box(M[2], vs[0], yu + .5, xb, yu + 5.4)                          # substrate-tap bar, joined to the VSS strip
        ya, yb = max(yu + .7, o['dvss_band'][0] + .2), min(yu + 5.2, o['dvss_band'][1] - .2)
        if yb - ya >= .7: landing(xa + .2, ya, xb - .2, yb)
        box(M[2], xa, yu + 5.8, xb, yt)                                  # DVDD bar
        for b1, b2 in o['dvdd_bands']:
            ya, yb = max(yu + 6., b1 + .3), min(yt - .2, b2 - .3)
            if yb - ya >= .7:
                landing(xa + .2, ya, xb - .2, yb)
                if b2 - b1 > 20.: box(M[3], xb - .2, ya, xl + .2, yb)        # band-134 landing over the neck to the right DVDD bar
    # ---- optional down-row fingers left of the neck (n_dn_left)
    ndl = int(o.get('n_dn_left', 0))
    if ndl:
        vs = o.get('vss_strip')
        if not vs: raise ValueError('n_dn_left needs vss_strip (the VSS bar joins it)')
        fxd = [n1 - 4.5 - o['pitch'] * i for i in range(ndl)]
        xa, xb = min(fxd) - 2., max(fxd) + 2.
        if xa < vs[1] + 2.5: raise ValueError(f'n_dn_left: fingers reach the VSS strip ({xa} < {vs[1] + 2.5})')
        for x in fxd:
            cell.insert(k.DCellInstArray(nd.cell_index(), k.DTrans(x0 + x, yd)))
            for dy in range(1, nb + 1): via1(x, yd - dy)
            for dy in range(1, 12):
                for s_ in (-1.03, 1.03): via1(x + s_, yd + dy)
        box(M[2], xa, o['plate_y'], n1 + 1., yd - .5)                    # PAD plate + bar from the bond pad plate / neck
        box(M[2], vs[0], yd + .5, xb, yd + 18.5)                         # VSS bar, joined to the VSS strip
        landing(xa + .2, yd + .7, xb - .2, yd + 18.3)
    # ---- Metal1 bridge under the neck: VSS bar -> the family's VSS Metal2 strip
    if o.get('vss_strip'):
        v1, v2 = o['vss_strip']; a = max(v1 + .3, v2 - 3.3); y1, y2 = yd + 14.3, yd + 17.
        box(M[1], a, y1, xl + 3., y2)
        box(M[2], a, y1, v2 - .3, y2); varray(1, a, y1, v2 - .3, y2)        # Metal2 lies inside the strip
        varray(1, xl, y1, xl + 3., y2)
    return dict(dvdd_label=lab, vss_label=(x0 + (xl + xr) / 2, yd + 9.5), pad_label=(x0 + (n1 + n2) / 2, o['plate_y'] + 1.),
                fingers_x=[x0 + x for x in fx], n_dn=ndn, n_up=nup, n_up_left=nlu, n_dn_left=ndl, cuts=cnt,
                bbox=[x0 + min(nl, (o.get('vss_strip') or (nl,))[0]), o['plate_y'], x0 + xs, yt])



def assemble(work):
    """Inside the layout image: the standalone test cell."""
    import klayout.db as k
    o = json.loads((work / 'site-config.json').read_text())
    l = k.Layout(); l.dbu = .001
    load_primitives(l, work)
    root = l.create_cell('pad_site_primary')
    info = draw(l, root, 0., o)
    def box(layer, x1, y1, x2, y2): root.shapes(l.layer(layer, 0)).insert(k.DBox(x1, y1, x2, y2))
    n1, n2 = o['neck']
    box(M[2], 3.5, 56., 71.5, 65.325)                                 # bond pad plate stub
    box(M[2], n1, 56., n2, o['y_vdd_top'] + 6.)                       # neck stub
    if o.get('vss_strip'): box(M[2], o['vss_strip'][0], 74.305, o['vss_strip'][1], o['y_vdd_top'] + 6.)
    T = lambda name, m, p: root.shapes(l.layer(M[m], 10)).insert(k.DText(name, k.DTrans(p[0], p[1])))
    T('PAD', 2, info['pad_label']); T('VSS', 2, info['vss_label']); T('DVDD', 3, info['dvdd_label'])
    l.write(str(work / 'pad_site_primary.gds'))
    (work / 'site-info.json').write_text(json.dumps(info, indent=1) + '\n')


def generate(work, opt):
    sys.path.insert(0, str(HERE))
    from layout import magic, IMAGE
    from run_first_pass import lvs
    work.mkdir(parents=True, exist_ok=False)
    o = dict(OPT); o.update(opt)
    (work / 'site-config.json').write_text(json.dumps(o, indent=1) + '\n')
    for n in (ND, PD): shutil.copy(PRIM / f'{n}.gds', work / f'{n}.gds')
    shutil.copy(Path(__file__), work / 'pad_site_primary.py')
    subprocess.run(['docker', 'run', '--rm', '--network', 'none', '--entrypoint', 'python3', '--mount', f'type=bind,src={work},dst=/work', IMAGE,
                    '/work/pad_site_primary.py', '--inside', '/work'], check=True)
    (work / 'extract.tcl').write_text('crashbackups stop\ngds read pad_site_primary.gds\nload pad_site_primary\nselect top cell\nflatten pad_site_primary_flat\n'
        'load pad_site_primary_flat\nsave\nselect top cell\nexpand\ndrc check\ndrc catchup\nputs "SITE_DRC [drc list count total]"\nputs [drc listall why]\n'
        'extract all\next2spice lvs\next2spice\nquit -noprompt\n')
    res = magic(work, 'extract.tcl')
    drc = next((l for l in res.stdout.splitlines() if l.startswith('SITE_DRC')), 'SITE_DRC ?')
    ref = ['.subckt site_reference PAD VSS DVDD'] + reference_lines('S', 'PAD', 'VSS', 'DVDD', o) + ['.ends']
    (work / 'reference.spice').write_text('\n'.join(ref) + '\n')
    ok = lvs(work, 'pad_site_primary_flat.spice', 'pad_site_primary_flat', 'reference.spice', 'site_reference', 'lvs.txt')
    info = json.loads((work / 'site-info.json').read_text())
    rep = dict(drc=drc, lvs_match=bool(ok), config=o, info=info, gds_sha256=hashlib.sha256((work / 'pad_site_primary.gds').read_bytes()).hexdigest(),
               generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (work / 'site-report.json').write_text(json.dumps(rep, indent=1) + '\n')
    print(drc, 'LVS', ok)
    if drc != 'SITE_DRC 0' or not ok: raise SystemExit('pad-site primary failed DRC / LVS')


if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--inside':
        assemble(Path(sys.argv[2]))
    else:
        p = argparse.ArgumentParser()
        p.add_argument('--output-dir', type=Path, required=True)
        p.add_argument('--n-dn', type=int); p.add_argument('--n-up', type=int)
        p.add_argument('--neck', type=float, nargs=2); p.add_argument('--neck-extra-left', type=float)
        p.add_argument('--vss-strip', type=float, nargs=2); p.add_argument('--no-vss-bridge', action='store_true')
        p.add_argument('--pitch', type=float); p.add_argument('--first-x', type=float)
        p.add_argument('--opt-json', help='further OPT overrides as a JSON object')
        a = p.parse_args()
        opt = {k_: v for k_, v in dict(n_dn=a.n_dn, n_up=a.n_up, neck=a.neck, neck_extra_left=a.neck_extra_left, vss_strip=a.vss_strip,
                                       pitch=a.pitch, first_x=a.first_x).items() if v is not None}
        if a.no_vss_bridge: opt['vss_strip'] = None
        if a.opt_json: opt.update(json.loads(a.opt_json))
        generate(a.output_dir.resolve(), opt)
