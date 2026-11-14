"""wtx_mux8 layout generator (8-phase one-hot muxing pre-driver, schematic = mux8.py).  NOT published.

    python3 mux8_layout.py            # everything -> scratch/wired_tx/s12/layout/out
    python3 mux8_layout.py slice      # the phase slice alone (DRC + LVS against its own schematic)
    python3 mux8_layout.py top neg    # top + negative-control LVS (two slice inputs swapped in the reference)
    python3 mux8_layout.py top kl     # top + KLayout DRC

Floorplan (bottom = input side, top = pad side), all device sizes from mux8.P:

    +-------------------- loads: per bank RL pair (outputs at the top edge), RCM, PMOS header -------------+
    | cap |  slice  slice  slice  slice  slice  slice  slice  slice    (phases in fold order 0 7 1 6 2 5 3 4)
    +-----+------------------------------------------------------------------------------------------------+

  wtx_mx_slice (one cell, eight identical instances), four abutted rows with shared rails:
      stack   MB / MP / MN of both banks in one NMOS strip (shared diffusion VSS-B-S-A-OUT-A-S-B-VSS), gate tracks
              on Metal1 below, the four output buses on Metal3 || Metal4 straight over the fingers
      preQ    POST bank pre-driver: TG, keeper, 2 x NOR, I2, I3            (row flipped)
      preM    MAIN bank pre-driver
      in      I0, trim switches + MOS caps, I0b, I1, static stream gating  (row flipped)
    Rows are compiled by XRow, a variant of timing's compact.Row (same column description and geometry) with what
    this cell needs and compact.Row lacks: tracks shared by nets that do not overlap, through tracks (static
    controls run through all eight slices by abutment), per-gate channel length (trim caps), no edge ports (inter-row
    nets are Metal3 columns over the cells).  The stack / header / pull-down devices use Strip (single-type finger
    array with electromigration-sized Metal1 / Metal2 strips).
  Only the ring nets leave a slice: B (to the previous phase's stack) and UP / VP (previous phase's POST data).
  With the fold order every such net spans two slice pitches or one; all are drawn as Metal4 tracks of the SAME
  length (the one-pitch ones get a dummy extension), on Metal3 columns that are part of the slice cell.
"""
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import mux8
import tools

sys.path.insert(0, str(tools.PROJECT / 'analog/timing'))
import compact  # noqa: E402  (row geometry constants)
import layout_engine as le  # noqa: E402

WORK = tools.SCRATCH / 's12' / 'layout'
OUT = WORK / 'out'
IMAGE, PDK = le.DIGITAL_IMAGE, le.PDK
L0, CW, TRACK_W, TRACK_P, RAIL_W = compact.L, compact.CW, compact.TRACK_W, compact.TRACK_P, compact.RAIL_W
TOP = 'wtx_mux8'
SLICE = 'wtx_mx_slice'
ORDER = [0, 7, 1, 6, 2, 5, 3, 4]          # phase at slice position p (fold: every ring hop is 1 or 2 pitches)


def s(v):
    return le.snap(v)


def docker(work, args, entry='/bin/sh', timeout=7200):
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--cpus', '1', '--memory', '8g', '-e', 'OMP_NUM_THREADS=1',
           '--entrypoint', entry, '--mount', f'type=bind,src={work},dst=/work', '-w', '/work', IMAGE] + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def magic(work, script):
    r = docker(work, ['-c', f'magic -dnull -noconsole -rcfile {PDK}/libs.tech/magic/gf180mcuD.magicrc /work/{script}'])
    (Path(work) / (script + '.log')).write_text(r.stdout + r.stderr)
    return r


def netgen(work, lay, lay_cell, sch, sch_cell, out='lvs.txt'):
    r = docker(work, ['-batch', 'lvs', f'{lay} {lay_cell}', f'{sch} {sch_cell}',
                      f'{PDK}/libs.tech/netgen/gf180mcuD_setup.tcl', out], entry='netgen')
    (Path(work) / (out + '.log')).write_text(r.stdout + r.stderr)
    text = (Path(work) / out).read_text() if (Path(work) / out).exists() else ''
    final = text[text.rfind('Final result'):] if 'Final result' in text else text[-1500:]
    ok = 'match uniquely' in final and 'mismatch' not in final.lower().replace('property errors', '')
    return dict(unique_match=ok, summary=final.strip()[:400], report=str(Path(work) / out))


# ------------------------------------------------------------------------------------------------ geometry
class Geo:
    def __init__(self):
        self.r, self.lab, self.cells = [], [], []

    def rect(self, layer, x1, y1, x2, y2):
        x1, x2 = sorted((s(x1), s(x2)))
        y1, y2 = sorted((s(y1), s(y2)))
        if x2 > x1 and y2 > y1:
            self.r.append((layer, x1, y1, x2, y2))

    def label(self, net, layer, x, y, port=None):
        self.lab.append((net, layer, s(x), s(y), port))

    def via(self, x, y, lo, hi):
        """single-cut stack, Metal lo .. Metal hi (pads as layout_engine.Layout.via)."""
        for m in range(lo, hi + 1):
            h = 0.19 if m == 1 else 0.22 if m == 5 else 0.2
            self.rect(f'metal{m}', x - h, y - h, x + h, y + h)
        for m in range(lo, hi):
            h = 0.13 if m == 1 else 0.14
            self.rect(f'via{m}', x - h, y - h, x + h, y + h)

    def varr(self, x1, y1, x2, y2, lo, hi, metal=True):
        """via array filling a rectangle, Metal lo .. Metal hi (Magic cuts the array).  Returns cuts per level."""
        for m in range(lo, hi + 1):
            if metal:
                self.rect(f'metal{m}', x1, y1, x2, y2)
        for m in range(lo, hi):
            e = 0.1 if m == 4 else 0.07
            self.rect(f'via{m}', x1 + e, y1 + e, x2 - e, y2 - e)
        n = lambda a: max(1, int((a - 0.14 - 0.26 + 0.26) / 0.52 + 1e-6))
        return n(abs(x2 - x1)) * n(abs(y2 - y1))

    def place(self, o, dx=0.0, dy=0.0, flip_h=None):
        """copy geometry of `o`; flip_h = row height: mirror in y about the row before the shift."""
        fy = (lambda y: flip_h - y) if flip_h is not None else (lambda y: y)
        for layer, x1, y1, x2, y2 in o.r:
            self.rect(layer, x1 + dx, fy(y1) + dy, x2 + dx, fy(y2) + dy)
        for net, layer, x, y, port in o.lab:
            self.label(net, layer, x + dx, fy(y) + dy, port)

    def tcl(self, cell, extra=()):
        c = ['crashbackups stop', f'load {cell}', 'units microns', 'snap internal']
        c += list(extra)
        for layer, x1, y1, x2, y2 in self.r:
            c += [f'box values {x1} {y1} {x2} {y2}', f'paint {layer}']
        for net, layer, x, y, port in self.lab:
            c += [f'box values {s(x - 0.1)} {s(y - 0.1)} {s(x + 0.1)} {s(y + 0.1)}', f'label {net} FreeSans 0.2 0 0 0 c {layer}']
            if port is not None:
                c.append(f'port make {port}')
        return c + ['save', 'quit -noprompt']


def C(n, p=None, same=True):
    return dict(k='c', n=n, p=(n if (same and p is None) else p))


def G(net, wn=None, wp=None, n=True, p=True, l=L0):
    d = dict(k='g', net=net, n=n, p=p, l=l)
    if wn is not None:
        d['wn'] = wn
    if wp is not None:
        d['wp'] = wp
    return d


BRK = dict(k='c', n='-', p='-')
RAILV = C('VSS', 'VDD', same=False)


def nfing(w, wmax):
    """finger count: w / nf <= wmax and on the 5 nm grid."""
    nf = max(1, math.ceil(w / wmax - 1e-9))
    while abs(round(w / nf * 200) - w / nf * 200) > 1e-6:
        nf += 1
        if nf > 400:
            raise ValueError(f'no finger split for w={w}')
    return nf


def fet(name, kind, d, g, s_, w, l=L0):
    b, m = ('VSS', 'nfet_03v3') if kind == 'n' else ('VDD', 'pfet_03v3')
    return f'X{name} {d} {g} {s_} {b} {m} w={w:g}u l={l:g}u'


# ------------------------------------------------------------------------------------------------ rows
class XRow:
    """compact.Row geometry (same column dicts) + shared tracks, through tracks, per-gate length, over-cell access."""

    def __init__(self, name, cols, wn, wp, order=(), through=(), min_width=0.0, min_tracks=0, tracks=None):
        self.name, self.cols, self.wn, self.wp = name, cols, wn, wp
        self.order, self.through, self.min_width, self.min_tracks = list(order), list(through), min_width, min_tracks
        self.tracks = tracks        # explicit {net: track index} (hand-packed); None = automatic order-preserving packing

    # -- column x positions with the gate/contact spacings of compact.Row.build
    def _tight(self, spots):
        cols, x = self.cols, [0.6]
        for i in range(1, len(cols)):
            a, b = cols[i - 1], cols[i]
            if a['k'] == 'g' and b['k'] == 'g':
                dx = 0.52
            elif a['k'] == 'c' and b['k'] == 'c':
                dx = 0.65
            elif (i in spots and b['k'] == 'c') or (i - 1 in spots and a['k'] == 'c'):
                dx = 0.65
            else:
                dx = 0.44
            for c in (a, b):
                if c['k'] == 'g':
                    dx += (c.get('l', L0) - L0) / 2
            x.append(s(x[-1] + dx))
        return x

    def build(self):
        a = self._build(None, self.tracks)
        # pack: a net keeps its vertical order against every net it comes close to, and may share a track otherwise
        tidx, done = {}, []
        for n in a['nets']:
            lo, hi = a['span'][n]
            t = 0
            for m in done:
                mlo, mhi = a['span'][m]
                if lo - 4 <= mhi and mlo - 4 <= hi:
                    t = max(t, tidx[m] + 1)
            tidx[n] = t
            done.append(n)
        if self.tracks:
            missing = [n for n in a['nets'] if n not in self.tracks]
            if missing:
                raise ValueError(f'{self.name}: no track for {missing}')
            tidx = dict(self.tracks)
        b = self._build(None, tidx)
        c = self._build(self._tight(set(b['spots'])), tidx)
        if set(c['spots']) != set(b['spots']):
            raise ValueError(f'{self.name}: poly-contact columns moved between passes')
        self.__dict__.update(c)
        # no two nets of one track closer than 0.3 um
        by = {}
        for n, (lo, hi) in self.ext.items():
            by.setdefault(self.track[n], []).append((lo, hi, n))
        for y, v in by.items():
            v.sort()
            for (l1, h1, n1), (l2, h2, n2) in zip(v, v[1:]):
                if l2 - h1 < 0.3:
                    raise ValueError(f'{self.name}: track clash {n1} / {n2}')
        return self

    def _build(self, xpos, tidx):
        cols = self.cols
        x = xpos or [0.6 + i * compact.PITCH / 2 for i in range(len(cols))]
        g, spots = Geo(), []
        wn, wp = [], []
        for i, c in enumerate(cols):
            if c['k'] == 'g':
                wn.append(c.get('wn', self.wn) if c.get('n', True) else 0)
                wp.append(c.get('wp', self.wp) if c.get('p', True) else 0)
            else:
                nb = [cols[j] for j in (i - 1, i + 1) if 0 <= j < len(cols) and cols[j]['k'] == 'g']
                wn.append(max([b.get('wn', self.wn) for b in nb if b.get('n', True)] or [self.wn]))
                wp.append(max([b.get('wp', self.wp) for b in nb if b.get('p', True)] or [self.wp]))
        y_tapn = 0.3
        yn0 = y_tapn + RAIL_W / 2 + 0.55
        yn1 = yn0 + max(max(wn), self.wn)
        nets = []

        def add(n):
            if n and n not in ('-', 'VSS', 'VDD') and n not in nets:
                nets.append(n)
        for c in cols:
            if c['k'] == 'c':
                add(c.get('n'))
                add(c.get('p'))
            else:
                add(c['net'])
        for n in self.through:
            add(n)
        nets = [n for n in self.order if n in nets] + [n for n in nets if n not in self.order]
        if tidx is None:
            tidx = {n: i for i, n in enumerate(nets)}
        nt = max(max(tidx.values(), default=-1) + 1, self.min_tracks, 1)
        track = {n: s(yn1 + 0.75 + TRACK_P * tidx[n]) for n in nets}
        gap_top = yn1 + 0.75 + TRACK_P * (nt - 1) + 0.55
        ynw = gap_top + 0.15
        yp0 = max(ynw + 0.45, yn1 + 0.9)
        yp1 = yp0 + max(max(wp), self.wp)
        y_tapp = yp1 + 0.55 + RAIL_W / 2
        width = max(x[-1] + 0.6, self.min_width)
        top = y_tapp + 0.3
        g.rect('metal1', 0, y_tapn - RAIL_W / 2, width, y_tapn + RAIL_W / 2)
        g.rect('psubdiff', 0.45, y_tapn - 0.25, width - 0.45, y_tapn + 0.25)
        g.rect('psubdiffcont', 0.55, y_tapn - 0.115, width - 0.55, y_tapn + 0.115)
        g.rect('nwell', -0.3, ynw, width + 0.3, top + 0.6)
        g.rect('metal1', 0, y_tapp - RAIL_W / 2, width, y_tapp + RAIL_W / 2)
        g.rect('nsubdiff', 0.45, y_tapp - 0.25, width - 0.45, y_tapp + 0.25)
        g.rect('nsubdiffcont', 0.55, y_tapp - 0.115, width - 0.55, y_tapp + 0.115)

        def islands(side):
            res, cur = [], []
            for i, c in enumerate(cols):
                present = (c.get(side, True) not in ('-', False)) if c['k'] == 'c' else bool(c.get(side, True))
                if present:
                    cur.append(i)
                else:
                    if cur:
                        res.append(cur)
                    cur = []
            if cur:
                res.append(cur)
            return res
        for side, layer, y0, ws in (('n', 'ndiff', yn0, wn), ('p', 'pdiff', yp0, wp)):
            for isl in islands(side):
                for i in isl:
                    if cols[i]['k'] == 'g' and i in (isl[0], isl[-1]):
                        raise ValueError(f'{self.name}: diffusion island must end on a contact column (col {i})')
                    core = CW / 2 + 0.07
                    xl = x[i] - (core if i == isl[0] else (x[i] - x[i - 1]) / 2)
                    xr = x[i] + (core if i == isl[-1] else (x[i + 1] - x[i]) / 2)
                    if cols[i]['k'] == 'c':
                        g.rect(layer, x[i] - core, y0, x[i] + core, y0 + ws[i])
                        if i != isl[0]:
                            g.rect(layer, xl, y0, x[i] - core, y0 + min(ws[i], ws[i - 1]))
                        if i != isl[-1]:
                            g.rect(layer, x[i] + core, y0, xr, y0 + min(ws[i], ws[i + 1]))
                        continue
                    g.rect(layer, xl, y0, xr, y0 + ws[i])
        used, vias, span = {}, {}, {}

        def see(net, i):
            lo, hi = span.get(net, (i, i))
            span[net] = (min(lo, i), max(hi, i))

        def via1(xx, yy):
            g.rect('metal1', xx - 0.19, yy - 0.19, xx + 0.19, yy + 0.19)
            g.rect('via1', xx - 0.13, yy - 0.13, xx + 0.13, yy + 0.13)
            g.rect('metal2', xx - 0.2, yy - 0.2, xx + 0.2, yy + 0.2)
        for i, c in enumerate(cols):
            if c['k'] != 'c':
                continue
            for side, ctype, y0, ws, rail_y, rail in (('n', 'ndiffc', yn0, wn, y_tapn, 'VSS'),
                                                      ('p', 'pdiffc', yp0, wp, y_tapp, 'VDD')):
                net = c.get(side)
                if net in (None, '-'):
                    continue
                w = ws[i]
                g.rect(ctype, x[i] - CW / 2, y0 + 0.065, x[i] + CW / 2, y0 + w - 0.065)
                g.rect('metal1', x[i] - CW / 2, y0, x[i] + CW / 2, y0 + w)
                if net == rail:
                    g.rect('metal1', x[i] - CW / 2, min(rail_y, y0 + 0.07), x[i] + CW / 2, max(rail_y, y0 + w - 0.07))
                elif net in ('VSS', 'VDD'):
                    raise ValueError(f'{self.name}: wrong rail on column {i}')
                else:
                    ty = track[net]
                    if side == 'n':
                        g.rect('metal1', x[i] - CW / 2, y0 + 0.07, x[i] + CW / 2, ty)
                        used.setdefault(i, []).append((y0, ty + 0.2))
                    else:
                        g.rect('metal1', x[i] - CW / 2, ty, x[i] + CW / 2, y0 + w - 0.07)
                        used.setdefault(i, []).append((ty - 0.2, y0 + w))
                    via1(x[i], ty)
                    vias.setdefault(net, []).append(x[i])
                    see(net, i)
        for i, c in enumerate(cols):
            if c['k'] != 'g':
                continue
            net, lg = c['net'], c.get('l', L0)
            hn, hp = c.get('n', True), c.get('p', True)
            ty = track[net]
            yb = yn0 - 0.22 if hn else ty - 0.18
            yt = yp0 + wp[i] + 0.22 if hp else ty + 0.18
            g.rect('polysilicon', x[i] - lg / 2, yb, x[i] + lg / 2, yt)
            spot, reuse = None, False
            for j in (i - 1, i + 1):
                if 0 <= j < len(cols) and cols[j]['k'] == 'c' and (net, ty) in used.get(('pcn', j), []):
                    spot, reuse = j, True
                    break
            if spot is None:
                for j in (i + 1, i - 1):
                    if 0 <= j < len(cols) and cols[j]['k'] == 'c':
                        if all(ty + 0.45 < a or ty - 0.45 > b for a, b in used.get(j, [])) and \
                                all(abs(ty - yy) > 0.6 for yy in used.get(('pc', j), [])):
                            spot = j
                            break
            if spot is None:
                raise ValueError(f'{self.name}: no free poly-contact spot for gate column {i} ({net})')
            xc = x[spot]
            spots.append(spot)
            see(net, spot)
            g.rect('polysilicon', min(x[i], xc) - 0.18, ty - 0.18, max(x[i], xc) + 0.18, ty + 0.18)
            if reuse:
                continue
            used.setdefault(('pc', spot), []).append(ty)
            used.setdefault(('pcn', spot), []).append((net, ty))
            g.rect('polycontact', xc - 0.115, ty - 0.115, xc + 0.115, ty + 0.115)
            via1(xc, ty)
            vias.setdefault(net, []).append(xc)
        ext = {}
        for n in nets:
            xs = vias.get(n, [])
            if n in self.through:
                lo, hi = 0.2, width - 0.2
                span[n] = (-10 ** 6, 10 ** 6)
            elif xs:
                lo, hi = min(xs), max(xs)
            else:
                raise ValueError(f'{self.name}: net {n} has no contact')
            g.rect('metal2', lo - 0.2, track[n] - TRACK_W / 2, hi + 0.2, track[n] + TRACK_W / 2)
            ext[n] = (lo - 0.2, hi + 0.2)
        return dict(geo=g, spots=spots, nets=nets, span=span, track=track, ext=ext, width=width, top=top, x=x,
                    ntracks=nt)

    # -- over-cell access: extend the net's Metal2 track to x (None if another net of the track is in the way)
    def reach(self, net, xx, apply=False):
        lo, hi = self.ext[net]
        nlo, nhi = min(lo, xx - 0.2), max(hi, xx + 0.2)
        if nlo >= lo and nhi <= hi:
            return 0.0
        for m, (a, b) in self.ext.items():
            if m != net and self.track[m] == self.track[net] and nlo - 0.3 < b and a - 0.3 < nhi:
                return None
        if nlo < 0.15 or nhi > self.width - 0.15:
            return None
        cost = (lo - nlo) + (nhi - hi)
        if apply:
            self.geo.rect('metal2', nlo, self.track[net] - TRACK_W / 2, nhi, self.track[net] + TRACK_W / 2)
            self.ext[net] = (nlo, nhi)
        return cost


def join(cols, c):
    if cols:
        if cols[-1] == c[0]:
            c = c[1:]
        else:
            cols.append(BRK)
    cols += c


def g_inv(pre, a, y, wn, wp, WN, WP):
    """inverter; N and P finger counts independent (N-heavy / P-heavy drivers)."""
    nfn, nfp = nfing(wn, WN), nfing(wp, WP)
    ng = max(nfn, nfp)
    cols, net = [], []
    for j in range(ng + 1):
        hn = j - 1 < nfn and j >= 1 or j < nfn
        hp = j - 1 < nfp and j >= 1 or j < nfp
        cols.append(dict(k='c', n=(('VSS' if j % 2 == 0 else y) if hn else '-'), p=(('VDD' if j % 2 == 0 else y) if hp else '-')))
        if j < ng:
            cols.append(G(a, wn / nfn, wp / nfp, n=j < nfn, p=j < nfp))
    net += [fet(f'{pre}n{f}', 'n', y, a, 'VSS', wn / nfn) for f in range(nfn)]
    net += [fet(f'{pre}p{f}', 'p', y, a, 'VDD', wp / nfp) for f in range(nfp)]
    return cols, net


def g_nand2(pre, a, b, y, wn, wp, WN, WP):
    """a next to the output; with more than one finger the series node is contacted and strapped (one net)."""
    nf = max(nfing(wn, WN), nfing(wp, WP))
    while abs(round(wn / nf * 200) - wn / nf * 200) > 1e-6 or abs(round(wp / nf * 200) - wp / nf * 200) > 1e-6:
        nf += 1
    n, p = wn / nf, wp / nf
    m = f'{pre}m'
    cols, net = [RAILV], []
    for f in range(nf):
        mid = dict(k='c', n=(m if nf > 1 else None), p=y)
        if f % 2 == 0:
            cols += [G(b, n, p), mid, G(a, n, p), C(y, 'VDD', same=False)]
        else:
            cols += [G(a, n, p), mid, G(b, n, p), RAILV]
        net += [fet(f'{pre}na{f}', 'n', y, a, m, n), fet(f'{pre}nb{f}', 'n', m, b, 'VSS', n),
                fet(f'{pre}pa{f}', 'p', y, a, 'VDD', p), fet(f'{pre}pb{f}', 'p', y, b, 'VDD', p)]
    return cols, net


def g_nor2(pre, a, b, y, wn, wp, WN, WP):
    """NOR2, a (clock) next to the output in the PMOS stack; the PMOS series node is contacted and strapped.
    One NMOS finger per input, under the two middle PMOS columns of the first finger pair."""
    nfp = nfing(wp, WP)
    if nfp % 2:
        nfp += 1
        while abs(round(wp / nfp * 200) - wp / nfp * 200) > 1e-6:
            nfp += 2
    if wn > WN:
        raise ValueError('g_nor2: NMOS wider than one finger')
    p = wp / nfp
    m = f'{pre}m'
    gates = []
    for f in range(nfp):
        gates += [b, a] if f % 2 == 0 else [a, b]
    pc = []
    for f in range(nfp):
        pc += ['VDD', m] if f % 2 == 0 else [y, m]
    pc.append('VDD')
    cols = []
    for j, gn in enumerate(gates):
        nn = {2: y, 3: 'VSS', 4: y}.get(j, '-')
        cols.append(dict(k='c', n=nn, p=pc[j]))
        has_n = j in (2, 3)
        cols.append(G(gn, wn if has_n else None, p, n=has_n))
    cols.append(dict(k='c', n=(y if len(gates) == 4 else '-'), p=pc[len(gates)]))
    net = [fet(f'{pre}na', 'n', y, a, 'VSS', wn), fet(f'{pre}nb', 'n', y, b, 'VSS', wn)]
    for f in range(nfp):
        net += [fet(f'{pre}pb{f}', 'p', m, b, 'VDD', p), fet(f'{pre}pa{f}', 'p', y, a, m, p)]
    return cols, net


def row_in(P, min_width=0.0):
    """phase input chain: I0, trim switches + MOS caps, I0b, I1."""
    WN, WP = 4.0, 8.0
    cols, net = [], []
    c, n = g_inv('i0', 'PH', 'Y', *P['i0'], WN, WP)
    join(cols, c)
    net += n
    # trim switches Y -> YC b (1, 2, 4 um) and MOS caps (gate YC b, source = drain = VSS, l = ctrim[1])
    wc, lc = P['ctrim']
    ts = [dict(k='c', n='YC0', p='-'), G('TR0', 1.0, p=False), dict(k='c', n='Y', p='-'), G('TR1', 2.0, p=False),
          dict(k='c', n='YC1', p='-'), BRK, dict(k='c', n='Y', p='-'), G('TR2', 4.0, p=False), dict(k='c', n='YC2', p='-')]
    join(cols, ts)
    net += [fet(f'ts{b}', 'n', 'Y', f'TR{b}', f'YC{b}', 2 ** b) for b in range(3)]
    cap = [dict(k='c', n='VSS', p='-')]
    for b in range(3):
        nf = nfing(wc * 2 ** b, WN)
        for f in range(nf):
            cap += [G(f'YC{b}', wc * 2 ** b / nf, p=False, l=lc), dict(k='c', n='VSS', p='-')]
            net.append(fet(f'tc{b}_{f}', 'n', 'VSS', f'YC{b}', 'VSS', wc * 2 ** b / nf, lc))
    join(cols, cap)
    for pre, a, y, key in (('i0b', 'Y', 'Z', 'i0b'), ('i1', 'Z', 'X', 'i1')):
        c, n = g_inv(pre, a, y, *P[key], WN, WP)
        join(cols, c)
        net += n
    tr = dict(Y=0, YC0=1, Z=1, YC1=2, X=2, YC2=3, PH=4, TR0=4, TR1=4, TR2=4)
    return XRow('in', cols, WN, WP, min_width=min_width, tracks=tr), net


def row_gate(P, min_width=0.0):
    """static stream gating of one phase (eighth-rate data): FB, U / V (MAIN), FP = F xor POL, UP / VP (POST)."""
    gw = P['gate']
    WN, WP = gw
    cols, net = [], []
    # order: U under the first NOR of the pre-driver rows, V under the second (straight Metal3 columns)
    for kind, pre, *pins in (('i', 'gf', 'F', 'FB'), ('n', 'gx1', 'F', 'POLB', 'N1'), ('n', 'gx2', 'FB', 'POL', 'N2'),
                             ('n', 'gx3', 'N1', 'N2', 'FP'), ('n', 'gu', 'F', 'ENM', 'UO'), ('i', 'gx4', 'FP', 'FPB'),
                             ('n', 'gp', 'FP', 'ENP', 'UPO'), ('n', 'gq', 'FPB', 'ENP', 'VPO'), ('n', 'gv', 'FB', 'ENM', 'VO')):
        c, n = (g_inv if kind == 'i' else g_nand2)(pre, *pins, *gw, WN, WP)
        join(cols, c)
        net += n
    tr = dict(F=0, UPO=0, VPO=0, FB=1, N1=2, UO=2, FPB=2, VO=2, N2=3, FP=3, ENM=4, ENP=5, POL=6, POLB=7)
    return XRow('gate', cols, WN, WP, through=['ENM', 'ENP', 'POL', 'POLB'], min_width=min_width, tracks=tr), net


def row_pre(P, tag, min_width=0.0):
    """pre-driver of one bank: TG + keeper, the two NORs, I2 (NAND) and I3.  Local names: XT, AP, AN, E, BO."""
    WN, WP = 8.0, 12.0
    en, enb, u, v = ('EN_MAIN', 'ENBM', 'UO', 'VO') if tag == 'M' else ('EN_POST', 'ENBQ', 'UPI', 'VPI')
    t = tag
    xt, ap, an, e, bo = f'XT{t}', f'AP{t}', f'AN{t}', f'E{t}', f'B{t}O'
    cols, net = [], []
    # I3 first (left), then I2, TG, NORs: the stack inputs AP / AN / B leave upwards
    c, n = g_inv(f'i3{t}', e, bo, *P['i3'], WN, WP)
    join(cols, c)
    net += n
    c, n = g_nand2(f'i2{t}', 'X', en, e, 2 * P['i2'][0], P['i2'][1], WN, WP)
    join(cols, c)
    net += n
    wtn, wtp = P['tg']
    nfn, nfp = nfing(wtn, WN), nfing(wtp, WP)
    tg = []
    for f in range(nfn):
        tg += [dict(k='c', n=('X' if f % 2 == 0 else xt), p='-'), G(en, wtn / nfn, p=False)]
        net.append(fet(f'tgn{t}{f}', 'n', xt, en, 'X', wtn / nfn))
    tg += [dict(k='c', n=(xt if nfn % 2 else 'X'), p='-'), BRK]
    first = xt if nfp % 2 == 0 else 'X'          # the P chain ends on XT, where the keeper attaches
    for f in range(nfp):
        tg += [dict(k='c', n='-', p=(first if f % 2 == 0 else ('X' if first == xt else xt))), G(enb, None, wtp / nfp, n=False)]
        net.append(fet(f'tgp{t}{f}', 'p', xt, enb, 'X', wtp / nfp))
    tg += [dict(k='c', n='-', p=xt), G(en, None, 1.0, n=False), dict(k='c', n='-', p='VDD')]
    net.append(fet(f'tgk{t}', 'p', xt, en, 'VDD', 1.0))
    join(cols, tg)
    for pre, b_, y in ((f'np{t}', u, ap), (f'nn{t}', v, an)):
        c, n = g_nor2(pre, xt, b_, y, *P['nor'], WN, WP)
        join(cols, c)
        net += n
    tr = {enb: 0, 'X': 1, xt: 2, ap: 3, an: 3, e: 3, u: 4, v: 4, bo: 4, f'np{t}m': 5, f'nn{t}m': 5, en: 6}
    return XRow('pre' + t, cols, WN, WP, through=[en, enb], min_width=min_width, tracks=tr), net


# ------------------------------------------------------------------------------------------------ finger strips
BAR_H = 1.2      # Metal1 bar of an internal ('bar') node


class Strip:
    """Single-type finger array with shared diffusion and electromigration-sized strips.
    cols: ('c', net) / ('g', net, w) alternating.  Rail (tap + Metal1 || Metal2, height rail_h) at the bottom, then
    Metal1 gate tracks (gt: gate net -> track), then the fingers.  Source / drain roles:
      'down'  Metal2 strip (m2w) from the fingers over the gate tracks into the rail (+ Metal1 over the diffusion)
      'up'    Metal1 + Metal2 strip from the fingers up to up_to (buses / plates land on it)
      'bar'   Metal1 only, all columns of the net joined by a Metal1 bar above the fingers (internal node)"""

    def __init__(self, kind, cols, gt, roles, rail_h=2.4, m2w=1.1, up_to=None, top_rail=False, min_width=0.0, l=L0,
                 gate_bar=False):
        self.kind, self.cols, self.gt, self.roles, self.gate_bar = kind, cols, gt, roles, gate_bar
        self.rail_h, self.m2w, self.up_to, self.top_rail, self.min_width, self.l = rail_h, m2w, up_to, top_rail, min_width, l

    def build(self):
        g, cols = Geo(), self.cols
        x = [s(0.6 + 0.44 * i) for i in range(len(cols))]
        self.width = width = max(x[-1] + 0.6, self.min_width)
        nt = max(self.gt.values(), default=0) + 1
        self.yt = {n: s(self.rail_h + 0.5 + 0.7 * i) for n, i in self.gt.items()}
        self.yd0 = yd0 = s(self.rail_h + 0.5 + 0.7 * (nt - 1) + 0.75)
        if self.gate_bar:       # all gates on one poly bar between rail and fingers, contact pad right of the array
            self.yd0 = yd0 = s(self.rail_h + 0.9)
            self.pad = (s(x[-1] + 1.3), s(yd0 - 0.45))
        w = []
        for i, c in enumerate(cols):
            if c[0] == 'g':
                w.append(c[2])
            else:
                w.append(max(cols[j][2] for j in (i - 1, i + 1) if 0 <= j < len(cols)))
        self.wmax = wmax = max(w)
        diff, cont, tap, tapc = (('ndiff', 'ndiffc', 'psubdiff', 'psubdiffcont') if self.kind == 'n'
                                 else ('pdiff', 'pdiffc', 'nsubdiff', 'nsubdiffcont'))
        up_to = self.up_to if self.up_to is not None else yd0 + wmax + 1.5
        self.top = up_to
        if self.kind == 'p':
            g.rect('nwell', -0.3, -0.3, width + 0.3, yd0 + wmax + 0.6)
        g.rect('metal1', 0, 0, width, self.rail_h)
        g.rect('metal2', 0, 0, width, self.rail_h)
        g.rect(tap, 0.45, 0.05, width - 0.45, self.rail_h - 0.05)
        g.rect(tapc, 0.55, 0.185, width - 0.55, self.rail_h - 0.185)
        g.rect('via1', 0.3, 0.8, width - 0.3, self.rail_h - 0.2)
        if self.top_rail:
            ra, rb = up_to - 0.9, up_to - 0.3
            g.rect('metal1', 0, ra, width, rb)
            g.rect(tap, 0.45, ra + 0.05, width - 0.45, rb - 0.05)
            g.rect(tapc, 0.55, ra + 0.185, width - 0.55, rb - 0.185)
        core = CW / 2 + 0.07
        n = len(cols)
        for i, c in enumerate(cols):
            xl = x[i] - (core if i == 0 else 0.22)
            xr = x[i] + (core if i == n - 1 else 0.22)
            if c[0] == 'c':
                g.rect(diff, x[i] - core, yd0, x[i] + core, yd0 + w[i])
                if i:
                    g.rect(diff, xl, yd0, x[i] - core, yd0 + min(w[i], w[i - 1]))
                if i != n - 1:
                    g.rect(diff, x[i] + core, yd0, xr, yd0 + min(w[i], w[i + 1]))
            else:
                g.rect(diff, xl, yd0, xr, yd0 + w[i])
        self.col_x, self.gate_x, bars = {}, {}, {}
        ybar = yd0 + wmax + 0.3
        for i, c in enumerate(cols):
            if c[0] == 'c':
                net, role = c[1], self.roles[c[1]]
                self.col_x.setdefault(net, []).append(x[i])
                g.rect(cont, x[i] - CW / 2, yd0 + 0.065, x[i] + CW / 2, yd0 + w[i] - 0.065)
                if self.gate_bar:
                    y1, y2 = (0, yd0 + w[i]) if role == 'down' else (yd0, up_to)
                    g.rect('metal1', x[i] - 0.3, y1, x[i] + 0.3, y2)
                    g.rect('metal2', x[i] - 0.3, y1, x[i] + 0.3, y2)
                    g.rect('via1', x[i] - 0.13, yd0 + 0.1, x[i] + 0.13, yd0 + w[i] - 0.1)
                    continue
                hw = 0.3 if role == 'bar' else 0.2
                g.rect('metal1', x[i] - hw, yd0, x[i] + hw, (ybar + BAR_H) if role == 'bar' else yd0 + w[i])
                if role == 'bar':
                    lo, hi = bars.get(net, (x[i], x[i]))
                    bars[net] = (min(lo, x[i]), max(hi, x[i]))
                    continue
                g.rect('via1', x[i] - 0.13, yd0 + 0.1, x[i] + 0.13, yd0 + w[i] - 0.1)
                if role == 'down':
                    g.rect('metal2', x[i] - self.m2w / 2, 0, x[i] + self.m2w / 2, (up_to - 0.3) if self.top_rail else yd0 + w[i])
                    if self.top_rail:
                        g.rect('via1', x[i] - self.m2w / 2 + 0.1, up_to - 0.9 + 0.1, x[i] + self.m2w / 2 - 0.1, up_to - 0.3 - 0.1)
                else:
                    g.rect('metal2', x[i] - self.m2w / 2, yd0, x[i] + self.m2w / 2, up_to)
            elif self.gate_bar:
                g.rect('polysilicon', x[i] - self.l / 2, yd0 - 0.6, x[i] + self.l / 2, yd0 + w[i] + 0.22)
            else:
                net, yt = c[1], self.yt[c[1]]
                self.gate_x.setdefault(net, []).append(x[i])
                g.rect('polysilicon', x[i] - self.l / 2, yt - 0.18, x[i] + self.l / 2, yd0 + w[i] + 0.22)
                g.rect('polysilicon', x[i] - 0.18, yt - 0.18, x[i] + 0.18, yt + 0.18)
                g.rect('polycontact', x[i] - 0.115, yt - 0.115, x[i] + 0.115, yt + 0.115)
                g.rect('metal1', x[i] - 0.19, yt - 0.2, x[i] + 0.19, yt + 0.2)
        if self.gate_bar:
            px, py = self.pad
            g.rect('polysilicon', x[1] - self.l / 2, yd0 - 0.6, px + 0.18, yd0 - 0.3)
            g.rect('polysilicon', px - 0.18, py - 0.18, px + 0.18, py + 0.18)
            g.rect('polycontact', px - 0.115, py - 0.115, px + 0.115, py + 0.115)
            g.rect('metal1', px - 0.19, py - 0.19, px + 0.19, py + 0.19)
        for net, (lo, hi) in bars.items():
            g.rect('metal1', lo - 0.3, ybar, hi + 0.3, ybar + BAR_H)
        for net, xs in self.gate_x.items():      # every gate track spans the whole array (entry anywhere, equal track C)
            g.rect('metal1', x[0] - 0.19, self.yt[net] - 0.2, x[-1] + 0.19, self.yt[net] + 0.2)
        self.geo, self.x, self.w = g, x, w
        return self

    def devices(self, pre):
        mod = 'nfet_03v3' if self.kind == 'n' else 'pfet_03v3'
        body = 'VSS' if self.kind == 'n' else 'VDD'
        return [f'X{pre}{i} {self.cols[i - 1][1]} {c[1]} {self.cols[i + 1][1]} {body} {mod} w={c[2]:g}u l={self.l:g}u'
                for i, c in enumerate(self.cols) if c[0] == 'g']

    def entry_ok(self, net, xx):
        if not (self.x[0] <= xx <= self.x[-1]):
            return False
        return all(abs(xx - xv) >= self.m2w / 2 + 0.2 + 0.3 for n_, v in self.col_x.items() if self.roles[n_] == 'down' for xv in v)


def stack(P, min_width=0.0, bw=4.0):
    """both banks' pull-down stacks of one phase.  Per bank: VSS-B-S-AP-OUTN-AP-S-B-VSS-B-S-AN-OUTP-AN-S-B-VSS ..."""
    nfb = 4 * max(1, round(P['wb'] / 35.0))
    wbf, wtf = P['wb'] / nfb, P['wt'] / (nfb // 2)
    for v in (wbf, wtf):
        if abs(round(v * 200) - v * 200) > 1e-6:
            raise ValueError(f'stack finger width {v} off grid')
    cols, roles = [('c', 'VSS')], dict(VSS='down')
    gt = dict(BMI=0, BQI=1, APM=2, ANM=3, APQ=4, ANQ=5)
    for t, (op, on) in (('M', ('MAIN_P', 'MAIN_N')), ('Q', ('POST_P', 'POST_N'))):
        b_, ap, an, sn = f'B{t}I', f'AP{t}', f'AN{t}', f'S{t}'
        roles.update({sn: 'bar', op: 'up', on: 'up'})
        for d in range(nfb // 4):
            for a, o in ((ap, on), (an, op)):
                cols += [('g', b_, wbf), ('c', sn), ('g', a, wtf), ('c', o), ('g', a, wtf), ('c', sn), ('g', b_, wbf), ('c', 'VSS')]
    st = Strip('n', cols, gt, roles, min_width=min_width, top_rail=True)
    st.build()
    st.up_to = s(st.yd0 + 4 * bw + 3 * 0.6)
    st.build()
    st.bw = bw
    st.bus = {n: s(st.yd0 + i * (bw + 0.6)) for i, n in enumerate(('MAIN_P', 'MAIN_N', 'POST_P', 'POST_N'))}
    st.nfb = nfb
    return st, st.devices('mk')


# ------------------------------------------------------------------------------------------------ phase slice
SP = ['PH', 'F', 'TR0', 'TR1', 'TR2', 'ENM', 'ENP', 'POL', 'POLB', 'EN_MAIN', 'ENBM', 'EN_POST', 'ENBQ', 'UPI', 'VPI',
      'UPO', 'VPO', 'BMO', 'BMI', 'BQO', 'BQI', 'MAIN_P', 'MAIN_N', 'POST_P', 'POST_N', 'VDD', 'VSS']
RING = ['BM', 'BQ', 'UP', 'VP']         # nets that go to the neighbouring phase; 4 Metal4 tracks each
RT_P = dict(BM=1.44, BQ=1.44, UP=0.72, VP=0.72)     # ring track pitch (B: wide, little coupling between phases)


class Block:
    """abutted rows (+ finger strips) with Metal3 columns over the cells."""

    def setup(self, rows, flips, y0=0.0):
        y, self.rows = y0, {}
        for r, flip in zip(rows, flips):
            r.build()
            self.rows[r.name] = (r, s(y), flip)
            y += r.top - RAIL_W
        self.g, self.cols3, self.pin, self.strips, self.excl = Geo(), [], {}, {}, []
        return s(y)

    def ty(self, row, net):
        r, y0, flip = self.rows[row]
        return s(y0 + (r.top - r.track[net] if flip else r.track[net]))

    def free(self, xx, lo, hi):
        if xx < 0.6 or xx > self.W - 0.6:
            return False
        if any(xx + 0.5 > a and xx - 0.5 < b and hi + 0.3 > c and lo - 0.3 < d for a, b, c, d in self.excl):
            return False
        return not any(abs(cx - xx) < 0.72 and lo - 0.5 < b and a - 0.5 < hi for cx, a, b, _ in self.cols3)

    def column(self, net, terms, span=(), pref=None):
        """one Metal3 column joining `terms` ((row, net) or (strip, gate net)) and covering the y values in span."""
        best = None
        for k in range(int(self.W / 0.05)):
            xx = s(k * 0.05)
            cost, ys = 0.0, list(span)
            for row, n in terms:
                if row in self.strips:
                    st, x0, y0 = self.strips[row]
                    if not st.entry_ok(n, xx - x0):
                        cost = None
                        break
                    ys.append(s(y0 + st.yt[n]))
                else:
                    c = self.rows[row][0].reach(n, xx)
                    if c is None:
                        cost = None
                        break
                    cost += c
                    ys.append(self.ty(row, n))
            if cost is None or not self.free(xx, min(ys) - 0.2, max(ys) + 0.2):
                continue
            if pref is not None:
                cost += 0.05 * abs(xx - pref)
            if best is None or cost < best[0] - 1e-9:
                best = (cost, xx, min(ys), max(ys))
        if best is None:
            raise RuntimeError(f'{type(self).__name__}: no Metal3 column for {net}')
        _, xx, lo, hi = best
        for row, n in terms:
            if row in self.strips:
                st, x0, y0 = self.strips[row]
                self.g.via(xx, y0 + st.yt[n], 1, 3)
            else:
                self.rows[row][0].reach(n, xx, apply=True)
                self.g.via(xx, self.ty(row, n), 2, 3)
        self.g.rect('metal3', xx - 0.2, lo - 0.2, xx + 0.2, hi + 0.2)
        self.cols3.append((xx, lo - 0.2, hi + 0.2, net))
        self.pin[net] = (xx, s(lo - 0.2), s(hi + 0.2))

    def finish(self):
        for r, y0, flip in self.rows.values():
            self.g.place(r.geo, 0, y0, r.top if flip else None)
        for st, x0, y0 in self.strips.values():
            self.g.place(st.geo, x0, y0)

    def rail_m2(self):
        """Metal2 over every logic rail (rows have Metal1 rails only), Via1 row; the top's stacks start on Metal2."""
        for r, y0, flip in self.rows.values():
            for yr in (y0, y0 + r.top - RAIL_W):
                self.g.rect('metal2', 0, yr, self.W, yr + RAIL_W)
                self.g.rect('via1', 0.3, yr + 0.1, self.W - 0.3, yr + RAIL_W - 0.1)

    def bus_vias(self, key):
        st, x0, y0 = self.strips[key]
        for n, yb in self.bus.items():
            for xx in st.col_x.get(n, []):
                self.g.varr(x0 + xx - st.m2w / 2, y0 + yb + 0.1, x0 + xx + st.m2w / 2, y0 + yb + self.bw - 0.1, 2, 4)


VSS_W, VDD_W = 9.0, 5.0      # Metal5 strap widths (VSS on the slice boundaries, VDD inside every slice)
VSS_S, VDD_S = 1.5, 2.0      # half width of the via stacks on the logic rails
OUT_S = 5.4                  # half width of an output Metal5 strap (0.6 um to the header VDD straps, MT.2b)


class Slice(Block):
    def __init__(self, P):
        err = None
        for vx in (10.5, 9.5, 11.5, 8.5, 12.5, 7.5, 13.5, 6.0, 14.5, 16.0, 18.0, 20.0):     # Metal5 VDD strap position
            try:
                self.vdd_x = vx
                self.make(P)
                return
            except RuntimeError as e:
                err = e
        raise err

    def make(self, P):
        st, nst = stack(P)
        rows = [row_gate(P), row_in(P), row_pre(P, 'M'), row_pre(P, 'Q')]
        self.W = W = s(math.ceil(max([st.width] + [r.build().width for r, _ in rows]) * 2) / 2)
        st, nst = stack(P, W)
        rows = [row_gate(P, W), row_in(P, W), row_pre(P, 'M', W), row_pre(P, 'Q', W)]
        self.net = nst + [l for _, n in rows for l in n]
        self.ys = ys = self.setup([r for r, _ in rows], (False, True, False, True))
        self.st, self.bus, self.bw = st, st.bus, st.bw
        self.strips['stack'] = (st, 0.0, ys)
        self.H = s(ys + st.top + 0.3)
        # keep-outs for the top's power via stacks (Metal3 pads): VSS on both boundaries, wide on the stack rail; VDD
        for xb in (0.0, W):
            self.excl += [(xb - VSS_S - 0.3, xb + VSS_S + 0.3, 0, self.H), (xb - VSS_W / 2 + 0.1, xb + VSS_W / 2 - 0.1, ys - 0.1, ys + st.rail_h + 0.1)]
        self.excl.append((self.vdd_x - VDD_S - 0.3, self.vdd_x + VDD_S + 0.3, 0, ys - 1.0))
        # ring-track groups (Metal4, drawn by the top): B over the POST pre-driver row, UP / VP over the MAIN one
        yq, ym = self.rows['preQ'][1], self.rows['preM'][1]
        self.ring_y = {'BM': s(yq + 5.0), 'BQ': s(yq + 5.0 + 4 * RT_P['BM']), 'UP': s(ym + 12.0), 'VP': s(ym + 12.0 + 4 * RT_P['UP'])}
        self.route()
        self.finish()
        self.rail_m2()
        for n, yb in st.bus.items():
            for m in (3, 4):
                self.g.rect(f'metal{m}', 0, ys + yb, W, ys + yb + st.bw)
        self.bus_vias('stack')
        # names of the phase-path nets (extraction report)
        for row, nets in (('in', ('Y', 'Z', 'X')), ('preM', ('XTM', 'APM', 'ANM', 'EM')), ('preQ', ('XTQ', 'APQ', 'ANQ', 'EQ'))):
            for n in nets:
                self.g.label(n, 'metal2', self.rows[row][0].ext[n][0] + 0.2, self.ty(row, n))

    def route(self):
        ry = self.ring_y
        grp = lambda n: (ry[n], s(ry[n] + 3 * RT_P[n]))
        c = self.column
        c('X', [('in', 'X'), ('preM', 'X'), ('preQ', 'X')])
        c('APM', [('preM', 'APM'), ('stack', 'APM')])
        c('ANM', [('preM', 'ANM'), ('stack', 'ANM')])
        c('APQ', [('preQ', 'APQ'), ('stack', 'APQ')])
        c('ANQ', [('preQ', 'ANQ'), ('stack', 'ANQ')])
        c('BMO', [('preM', 'BMO')], grp('BM'))
        c('BMI', [('stack', 'BMI')], grp('BM'))
        c('BQO', [('preQ', 'BQO')], grp('BQ'))
        c('BQI', [('stack', 'BQI')], grp('BQ'))
        c('UO', [('gate', 'UO'), ('preM', 'UO')])
        c('VO', [('gate', 'VO'), ('preM', 'VO')])
        c('UPO', [('gate', 'UPO')], grp('UP'))
        c('VPO', [('gate', 'VPO')], grp('VP'))
        c('UPI', [('preQ', 'UPI')], grp('UP'))
        c('VPI', [('preQ', 'VPI')], grp('VP'))
        for n in ('PH', 'TR0', 'TR1', 'TR2'):
            c(n, [('in', n)], (0.2,))
        c('F', [('gate', 'F')], (0.2,))
        # static-control feeds for the top (header gates): columns from the through tracks up to the stack rail
        self.feed_y = s(self.ys + self.st.yd0 - 1.15)
        for n, row in (('ENBM', 'preM'), ('ENBQ', 'preQ')):
            c(n, [(row, n)], (self.feed_y,))

    def labels(self):
        """port labels for the stand-alone slice check."""
        g, i = Geo(), {n: k + 1 for k, n in enumerate(SP)}
        where = dict(PH='in', TR0='in', TR1='in', TR2='in', F='gate', ENM='gate', ENP='gate', POL='gate', POLB='gate',
                     UPO='gate', VPO='gate', EN_MAIN='preM', ENBM='preM', BMO='preM', EN_POST='preQ', ENBQ='preQ',
                     BQO='preQ', UPI='preQ', VPI='preQ')
        for n, row in where.items():
            g.label(n, 'metal2', self.rows[row][0].ext[n][0] + 0.2, self.ty(row, n), i[n])
        for n in ('BMI', 'BQI'):
            g.label(n, 'metal1', self.st.gate_x[n][0], self.ys + self.st.yt[n], i[n])
        for n, yb in self.st.bus.items():
            g.label(n, 'metal3', 1.0, self.ys + yb + 1.0, i[n])
        g.label('VSS', 'metal1', 0.3, 0.3, i['VSS'])
        g.label('VDD', 'metal1', 0.3, self.rows['in'][1] + 0.3, i['VDD'])
        g.label('VDD', 'metal1', 0.3, self.rows['preQ'][1] + 0.3, i['VDD'])     # second VDD rail (strapped by the top)
        return g

    def spice(self):
        return f'.subckt {SLICE} ' + ' '.join(SP) + '\n' + '\n'.join(self.net) + f'\n.ends {SLICE}\n'


CAP_W = 10.5


class Cap(Block):
    """left end column: POLB / ENB inverters in the rows of the slices (same tracks, so the static controls run
    through all slices), off-state pull-downs of the four outputs under the buses, control pins to the bottom edge."""

    def __init__(self, P, sl):
        self.W = W = CAP_W
        gw = P['gate']
        ref = sl.rows
        c, n1 = g_inv('ipol', 'POL', 'POLB', 1, 2, *gw)
        rg = XRow('gate', c, *gw, through=['ENM', 'ENP', 'POL', 'POLB'], min_width=W,
                  tracks={k: v for k, v in ref['gate'][0].tracks.items() if k in ('ENM', 'ENP', 'POL', 'POLB')},
                  min_tracks=ref['gate'][0].ntracks)
        ri = XRow('in', [BRK], 4.0, 8.0, min_width=W, min_tracks=ref['in'][0].ntracks)
        rows, self.net = [rg, ri], list(n1)
        for t, en, enb in (('M', 'EN_MAIN', 'ENBM'), ('Q', 'EN_POST', 'ENBQ')):
            c, n = g_inv(f'ie{t}', en, enb, 1, 2, 8.0, 12.0)
            rr = ref['pre' + t][0]
            rows.append(XRow('pre' + t, c, 8.0, 12.0, through=[en, enb], min_width=W, tracks={en: rr.tracks[en], enb: rr.tracks[enb]},
                             min_tracks=rr.ntracks))
            self.net += n
        ys = self.setup(rows, (False, True, False, True))
        for r, y0, _ in self.rows.values():
            if abs(r.top - ref[r.name][0].top) > 1e-6 or abs(y0 - ref[r.name][1]) > 1e-6:
                raise RuntimeError(f'cap row {r.name} does not line up with the slice rows')
        st = sl.st
        self.bus, self.bw, self.ys = sl.bus, sl.bw, ys
        nt = max(st.gt.values())
        for key, enb, op, on, x0, mw in (('pdM', 'ENBM', 'MAIN_P', 'MAIN_N', 0.0, 4.0), ('pdQ', 'ENBQ', 'POST_P', 'POST_N', 4.0, W - 4.0)):
            pd = Strip('n', [('c', op), ('g', enb, P['pd']), ('c', 'VSS'), ('g', enb, P['pd']), ('c', on)], {enb: nt},
                       {op: 'up', on: 'up', 'VSS': 'down'}, rail_h=st.rail_h, m2w=0.5, up_to=st.up_to, top_rail=True, min_width=mw)
            pd.build()
            if abs(pd.yd0 - st.yd0) > 1e-6:
                raise RuntimeError('cap strip does not line up with the stack')
            self.strips[key] = (pd, x0, ys)
            self.net += pd.devices(key)
        self.H = sl.H
        self.excl += [(W - VSS_S - 0.3, W + VSS_S + 0.3, 0, self.H), (W - VSS_W / 2 + 0.1, W + VSS_W / 2, ys - 0.1, ys + st.rail_h + 0.1)]
        for n in ('POL', 'ENM', 'ENP'):
            self.column(n, [('gate', n)], (0.2,))
        self.column('EN_MAIN', [('preM', 'EN_MAIN')], (0.2,))
        self.column('EN_POST', [('preQ', 'EN_POST')], (0.2,))
        self.column('ENBM', [('preM', 'ENBM'), ('pdM', 'ENBM')])
        self.column('ENBQ', [('preQ', 'ENBQ'), ('pdQ', 'ENBQ')])
        self.finish()
        self.rail_m2()
        for n, yb in self.bus.items():
            for m in (3, 4):
                self.g.rect(f'metal{m}', 0, ys + yb, W, ys + yb + self.bw)
        self.bus_vias('pdM')
        self.bus_vias('pdQ')
        self.g.rect('psubdiff', 0.45, ys + 0.05, W - 0.45, ys + st.rail_h - 0.05)       # one tap region (no notch between the strips)
        self.g.rect('psubdiffcont', 0.55, ys + 0.185, W - 0.55, ys + st.rail_h - 0.185)
        for a, b in ((ys + st.up_to - 0.9, ys + st.up_to - 0.3),):
            self.g.rect('psubdiff', 0.45, a + 0.05, W - 0.45, b - 0.05)
            self.g.rect('psubdiffcont', 0.55, a + 0.185, W - 0.55, b - 0.185)


def ring_plan():
    """Metal4 ring wires: for every phase k the wire from slice k to slice k-1 (B) / from k-1 to k (UP, VP), as
    (k, driver position, receiver position, lo position, hi position, track).  Every wire spans two slice pitches
    (one-pitch hops get a dummy extension past the receiver), four tracks."""
    pos = {k: p for p, k in enumerate(ORDER)}
    wires = []
    for k in range(8):
        d, r = pos[k], pos[(k - 1) % 8]
        lo, hi = min(d, r), max(d, r)
        if hi - lo == 1:
            e = r + (1 if r > d else -1)
            if not 0 <= e <= 7:
                e = d + (1 if d > r else -1)
            lo, hi = min(lo, e), max(hi, e)
        if hi - lo != 2:
            raise RuntimeError('fold order: ring hop longer than two pitches')
        wires.append([k, d, r, lo, hi, None])
    for w in sorted(wires, key=lambda w: (w[3], w[4])):
        used = {v[5] for v in wires if v[5] is not None and v[3] <= w[4] and w[3] <= v[4]}
        w[5] = min(t for t in range(8) if t not in used)
        if w[5] > 3:
            raise RuntimeError('ring wires need more than four tracks')
    return wires


def run_tcl(work, cell, cmds):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    if (work / f'{cell}.mag').exists():
        (work / f'{cell}.mag').unlink()
    (work / f'{cell}.tcl').write_text('\n'.join(cmds) + '\n')
    return magic(work, f'{cell}.tcl')


def build_slice(P=None, work=None):
    work = Path(work or WORK / 'slice')
    sl = Slice(dict(mux8.P, **(P or {})))
    g = Geo()
    g.place(sl.g)
    g.place(sl.labels())
    run_tcl(work, SLICE, g.tcl(SLICE))
    res = check(work, SLICE, sl.spice())
    res.update(size_um=[sl.W, sl.H], columns=len(sl.cols3))
    print(json.dumps(res, indent=1))
    return sl, res


# ------------------------------------------------------------------------------------------------ top
def gen_res(work, P):
    """ppolyf_u PCells WITHOUT guard ring (the ring's PPLUS sits 0.27 um from the resistor's: KLayout PP.2; same choice as
    rf_tx/layoutlib.py).  The substrate terminal is tied to VSS by tap strips beside each load cluster."""
    cmds = ['crashbackups stop', 'load primitive_workspace']
    for name, (w, l) in (('wtx_mx_rl', P['rl']), ('wtx_mx_rcm', P['rcm'])):
        cmds += ['units internal', f'set cell [magic::gencell_makecell gf180mcu::ppolyf_u w {w} l {l} guard 0 full_metal 0]',
                 'load $cell', f'save {name}', 'load primitive_workspace']
    (work / 'prim.tcl').write_text('\n'.join(cmds + ['quit -noprompt']) + '\n')
    magic(work, 'prim.tcl')
    out = {}
    for name in ('wtx_mx_rl', 'wtx_mx_rcm'):
        r = le.rects(work / f'{name}.mag')
        pc = sorted(r['polycontact'], key=lambda a: a[1])
        out[name] = dict(hx=pc[0][2], c0=(pc[0][1], pc[0][3]), c1=(pc[-1][1], pc[-1][3]),
                         py=max(a[3] for a in r['polysilicon']), body=max(a[3] for a in r['ppolyres']))
    return out


def build_top(P=None, neg=False, kl=False, work=None, out=True):
    P = dict(mux8.P, **(P or {}))
    work = Path(work or WORK / 'top')
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    sl = Slice(P)
    run_tcl(work, SLICE, sl.g.tcl(SLICE))
    ri = gen_res(work, P)
    cap = Cap(P, sl)
    X0, W, H, ys, st = cap.W, sl.W, sl.H, sl.ys, sl.st
    xs = lambda p_: s(X0 + p_ * W)
    pos = {k: p_ for p_, k in enumerate(ORDER)}
    g = Geo()
    g.place(cap.g)
    inst = []
    for p_, k in enumerate(ORDER):
        inst += [f'getcell {SLICE} child 0 0 parent {xs(p_)} 0', f'identify XS{k}']
    em = {}
    # ---- ring wires (Metal4), all of the same length
    for name, po, pi in (('BM', 'BMO', 'BMI'), ('BQ', 'BQO', 'BQI'), ('UP', 'UPI', 'UPO'), ('VP', 'VPI', 'VPO')):
        xa, xb = sl.pin[po][0], sl.pin[pi][0]
        for k, d, r, lo, hi, tr in ring_plan():
            y = s(sl.ring_y[name] + tr * RT_P[name])
            g.rect('metal4', xs(lo) + min(xa, xb) - 0.2, y - 0.2, xs(hi) + max(xa, xb) + 0.2, y + 0.2)
            g.via(xs(d) + xa, y, 3, 4)
            g.via(xs(r) + xb, y, 3, 4)
            g.label(f'{name}{(k - 1) % 8}', 'metal4', xs(lo) + min(xa, xb) + 0.5, y)
    # ---- power: Metal5 VSS straps on the slice boundaries, VDD straps inside the slices, via stacks on the rails
    y_vdd = [sl.rows['in'][1], sl.rows['preQ'][1]]
    y_vss = [0.0, sl.rows['preM'][1]]
    for p_ in range(9):
        xb = xs(p_)
        g.rect('metal5', xb - VSS_W / 2, 0, xb + VSS_W / 2, ys + st.rail_h)
        for yr in y_vss:
            em['vss_logic_cuts'] = g.varr(xb - VSS_S, yr + 0.05, xb + VSS_S, yr + 0.55, 2, 5)
        em['vss_strap_cuts'] = g.varr(xb - VSS_W / 2 + 0.2, ys + 0.2, xb + VSS_W / 2 - 0.2, ys + st.rail_h - 0.2, 2, 5)   # rail has its own Via1
    for p_ in range(8):
        xv = xs(p_) + sl.vdd_x
        g.rect('metal5', xv - VDD_W / 2, 0, xv + VDD_W / 2, y_vdd[1] + 0.9)
        for yr in y_vdd:
            em['vdd_logic_cuts'] = g.varr(xv - VDD_S, yr + 0.05, xv + VDD_S, yr + 0.55, 2, 5)
    # ---- loads: per bank header (bottom), RCM, RL pair (outputs at the top edge)
    xc = X0 + 4 * W
    y0 = s(H + 2.2)
    nfh = nfing(P['hdr'], 3.2)
    while nfh % 2 or abs(round(P['hdr'] / nfh * 200) - P['hdr'] / nfh * 200) > 1e-6:     # even: VDD on both ends
        nfh += 1
    wh = P['hdr'] / nfh
    hw = s(nfh * 0.44 + 0.6)          # half width of a header (and of a load cluster)
    cx = s(hw + 1.9)                  # cluster centres at xc -/+ cx
    net = list(cap.net)
    ports = {}
    rl, rc = ri['wtx_mx_rl'], ri['wtx_mx_rcm']
    for bi, (tag, xb, enb, op, on) in enumerate((('M', xc - cx, 'ENBM', 'MAIN_P', 'MAIN_N'), ('Q', xc + cx, 'ENBQ', 'POST_P', 'POST_N'))):
        top2, topn = f'TOP2{tag}', f'TOP{tag}'
        cols = [('c', 'VDD')]
        for f in range(nfh):
            cols += [('g', enb, wh), ('c', top2 if f % 2 == 0 else 'VDD')]
        hs = Strip('p', cols, {}, {'VDD': 'down', top2: 'up'}, rail_h=3.0, gate_bar=True)
        hs.build()
        hx0 = s(xb - (hs.x[0] + hs.x[-1]) / 2)
        g.place(hs.geo, hx0, y0)
        net += hs.devices(f'hp{tag}')
        g.varr(hx0 + 0.2, y0 + 0.2, hx0 + hs.width - 0.2, y0 + hs.rail_h - 0.2, 2, 4)        # rail also on Metal3 / Metal4
        yp0 = s(y0 + hs.yd0 + hs.wmax + 0.6)
        yr = s(yp0 + 1.3 + rc['py'])                                                          # RCM centre
        cmd = [f'getcell wtx_mx_rcm child 0 0 parent {s(xb)} {yr}', f'identify XRCM{tag}']
        # TOP2 plate: header drains -> RCM lower head (Metal1 || Metal2)
        xu = hs.col_x[top2]
        for m in (1, 2):
            g.rect(f'metal{m}', hx0 + xu[0] - 0.3, yp0, hx0 + xu[-1] + 0.3, yp0 + 1.0)
            g.rect(f'metal{m}', xb - rc['hx'], yp0 + 1.0, xb + rc['hx'], yr + rc['c0'][1] + 0.1)
        g.rect('via1', hx0 + xu[0], yp0 + 0.1, hx0 + xu[-1], yp0 + 0.9)
        # TOP plate: RCM upper head -> the lower heads of the two RL (Metal1 || Metal2; 2 um high where current turns)
        yw = s(yr + rc['py'] + 2.3)
        yl = s(yw + 0.2 + rl['py'])                                                           # RL centre
        xrl = {op: s(xb - 10.0), on: s(xb + 10.0)}
        for m in (1, 2):
            g.rect(f'metal{m}', xb - rc['hx'], yr + rc['c1'][0] - 0.1, xb + rc['hx'], yw)
        g.rect('via1', xb - rc['hx'] + 0.1, yr + rc['py'] + 0.3, xb + rc['hx'] - 0.1, yw - 0.1)
        for o, xr in xrl.items():
            inst += cmd + [f'getcell wtx_mx_rl child 0 0 parent {xr} {yl}', f'identify XRL{o[-1]}{tag}']
            cmd = []
            for m in (1, 2):
                g.rect(f'metal{m}', xr - rl['hx'], yw, xr + rl['hx'], yl + rl['c0'][1] + 0.1)
            # output pad on the upper head (Metal1 .. Metal5) and the Metal5 strap down to the bus
            ypad = s(yl + rl['c1'][0] - 0.1)
            ytop = s(yl + rl['py'] + 2.7)
            g.rect('metal1', xr - rl['hx'], ypad, xr + rl['hx'], ytop)
            em['rl_pad_cuts'] = g.varr(xr - rl['hx'], yl + rl['py'] + 0.3, xr + rl['hx'], ytop, 1, 5)
            yb = ys + sl.bus[o]
            g.rect('metal5', xr - OUT_S, yb, xr + OUT_S, ytop)
            em['bus_tap_cuts'] = g.varr(xr - rl['hx'], yb + 0.2, xr + rl['hx'], yb + sl.bw - 0.2, 4, 5)
            ports[o] = ('metal5', xr, ytop - 0.5)
        net += [f'XRCM{tag} {top2} {topn} VSS ppolyf_u r_width={P["rcm"][0]}u r_length={P["rcm"][1]}u',
                f'XRLP{tag} {topn} {op} VSS ppolyf_u r_width={P["rl"][0]}u r_length={P["rl"][1]}u',
                f'XRLN{tag} {topn} {on} VSS ppolyf_u r_width={P["rl"][0]}u r_length={P["rl"][1]}u']
        # header VDD: three Metal5 straps from the rail to the top edge
        for a, b in ((-hw, -16.0), (-4.0, 4.0), (16.0, hw)):
            g.rect('metal5', xb + a, y0 + 0.2, xb + b, ytop)
            g.varr(xb + a + 0.2, y0 + 0.4, xb + b - 0.2, y0 + hs.rail_h - 0.4, 4, 5)
            ports.setdefault('VDD', []).append(('metal5', s(xb + (a + b) / 2), ytop - 0.5))
        # substrate taps for the resistors (no guard rings): tap strips beside the cluster, on the slices' top VSS rail
        for xt in [s(xb - hw - 1.3)] + ([s(xb + hw + 2.5)] if tag == 'Q' else []):
            g.rect('psubdiff', xt - 0.25, H + 0.5, xt + 0.25, ytop)
            g.rect('psubdiffcont', xt - 0.115, H + 0.635, xt + 0.115, ytop - 0.135)
            g.rect('metal1', xt - 0.2, H - 1.0, xt + 0.2, ytop)
        # header gate: slice feed column -> Metal5 over the buses -> Metal3 jog -> poly pad
        px, py = s(hx0 + hs.pad[0]), s(y0 + hs.pad[1])
        fx = sl.pin[enb][0]
        blocked = [(xc + sg * cx + dx - 6.3, xc + sg * cx + dx + 6.3) for sg in (-1, 1) for dx in (-10.0, 10.0)]
        cand = [xs(p_) + fx for p_ in range(8) if not any(a < xs(p_) + fx < b for a, b in blocked)]
        xf = min(cand, key=lambda v: abs(v - px))
        yj = s(H + 0.5 + 0.8 * bi)
        g.via(xf, sl.feed_y, 3, 5)
        g.rect('metal5', xf - 0.22, sl.feed_y - 0.22, xf + 0.22, yj + 0.22)
        g.via(xf, yj, 3, 5)
        g.rect('metal3', min(xf, px) - 0.2, yj - 0.2, max(xf, px) + 0.2, yj + 0.2)
        g.rect('metal3', px - 0.2, yj - 0.2, px + 0.2, py + 0.2)
        g.via(px, py, 1, 3)
        em[f'hdr_{tag}'] = dict(fingers=nfh, w=wh, col_mA=2 * 20.0 / nfh, col_metal_um=1.2)
    Htop = ytop
    # ---- ports (order of mux8.PORTS)
    for p_, k in enumerate(ORDER):
        for n, name in [('PH', f'PH{k}'), ('F', f'F{k}')] + [(f'TR{b}', f'TR{k}_{b}') for b in range(3)]:
            ports[name] = ('metal3', xs(p_) + sl.pin[n][0], 0.2)
    for n in ('ENM', 'ENP', 'POL', 'EN_MAIN', 'EN_POST'):
        ports[n] = ('metal3', cap.pin[n][0], 0.2)
    ports['VDD'].append(('metal5', xs(0) + sl.vdd_x, 1.0))
    ports['VSS'] = ('metal5', xs(1), 1.0)
    for i, n in enumerate(mux8.PORTS):
        for layer, x, y in (ports[n] if isinstance(ports[n], list) else [ports[n]]):
            g.rect(layer, x - 0.2, y - 0.2, x + 0.2, y + 0.2)
            g.label(n, layer, x, y, i + 1)
    run_tcl(work, TOP, g.tcl(TOP, extra=inst))
    sch = '* reference: mux8.netlist()\n' + mux8.netlist(P)
    res = check(work, TOP, sch)
    res.update(size_um=[s(xs(8) + VSS_W / 2), s(Htop)], area_um2=round((xs(8) + VSS_W / 2) * Htop, 1),
               slice_um=[W, H], cap_um=[X0, H], loads_um=[s(2 * cx + 2 * hw + 1.2), s(Htop - H)], em=em)
    res['wire_c_fF'] = slice_caps(work / f'{TOP}.ext.spice')
    # ---- electromigration table (average mA, metal width um, mA/um) from the drawn geometry; 20 mA per bank
    nfb, bw = st.nfb, sl.bw
    frac = lambda xt: max((xt - X0) / W, 8 - (xt - X0) / W) * 20.0 / 16      # worse side of a bus tap, random data
    row = lambda i, w_: dict(mA=round(i, 3), metal_um=round(w_, 2), mA_per_um=round(i / w_, 2))
    res['em_table'] = {
        'stack VSS column (Metal2, 2 MB fingers)': row(2 * 2.5 / nfb, st.m2w),
        'stack VSS rail per slice (Metal1+2, to the two boundary straps)': row(0.57 * 5.0, 2 * st.rail_h),
        'VSS Metal5 strap (2 banks; + ~3 mA logic estimate)': row(5.0 + 3.0, VSS_W),
        'S column (Metal1; half of the slice current goes through metal, 1/8 duty)': row(20.0 / nfb / 8, 0.6),
        'S bar (Metal1, between finger groups)': row(2 * 20.0 / nfb / 8, BAR_H),
        'output column (Metal1+2, 2 MP/MN fingers, random data)': row(2 * 20.0 / (nfb // 2) / 16, 0.4 + st.m2w),
        'MAIN_P bus worst segment (Metal3+4)': row(frac(xc - cx - 10), 2 * bw), 'MAIN_N bus worst segment': row(frac(xc - cx + 10), 2 * bw),
        'POST_P bus worst segment': row(frac(xc + cx - 10), 2 * bw), 'POST_N bus worst segment': row(frac(xc + cx + 10), 2 * bw),
        'output Metal5 strap bus -> RL (per output)': row(10.0, 2 * OUT_S),
        'RL head (Metal1+2 tongue)': row(10.0, 2 * 2 * rl['hx']), 'TOP plate where current turns (Metal1+2, 2 um high)': row(2.5, 4.0),
        'RCM heads / TOP2 plate (Metal1+2)': row(20.0, 2 * 2 * rc['hx']),
        'header column (Metal1+2)': row(2 * 20.0 / nfh, 1.2), 'header VDD rail between straps (Metal1-4)': row(5.5, 4 * 3.0),
        'header VDD Metal5 straps (3 per bank)': row(20.0, 2 * (hw - 16.0) + 8.0),
        'logic VDD Metal5 strap per slice (~3 mA estimate)': row(3.0, VDD_W),
        'logic rails (Metal1+2, ~1.5 mA per rail and slice, two directions)': row(0.75, 2 * RAIL_W),
        'cuts': dict(vss_strap_stack=em['vss_strap_cuts'], rl_pad_stack=em['rl_pad_cuts'], bus_tap_via4=em['bus_tap_cuts'],
                     logic_vss_stack=em['vss_logic_cuts'], logic_vdd_stack=em['vdd_logic_cuts'], note='0.58 mA per cut assumed')}
    if neg:      # negative control: the reference with the inverter GF of phase 0 moved from F0 to F1 must NOT match
        bad = '\n'.join(l.replace(' F0 ', ' F1 ') if l.startswith('XGF_0') else l for l in sch.splitlines()) + '\n'
        (work / 'neg.sch.spice').write_text(bad)
        res['lvs_negative_control'] = netgen(work, f'{TOP}.lvs.spice', TOP, 'neg.sch.spice', TOP, out=f'{TOP}-lvs-neg.txt')
    if kl:
        gds = tools.gds_export_analog(work, TOP)
        res['klayout_drc'] = tools.klayout_drc(work, gds, TOP)
    (work / 'report.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    if not out:
        return res
    OUT.mkdir(parents=True, exist_ok=True)
    for f in [f'{TOP}.mag', f'{SLICE}.mag', 'wtx_mx_rl.mag', 'wtx_mx_rcm.mag', f'{TOP}.gds', f'{TOP}.ext.spice', f'{TOP}.lvs.spice',
              f'{TOP}.sch.spice', f'{TOP}-lvs.txt', f'{TOP}-lvs-neg.txt', 'drc-count.txt', 'drc-details.txt', 'report.json']:
        if (work / f).exists():
            shutil.copy(work / f, OUT / f)
    return res


def slice_caps(path):
    """total extracted wiring capacitance (to ground + coupling, fF; no device capacitance) of the phase-path nets,
    per phase, from the flat Magic netlist."""
    tot = {}
    for l in Path(path).read_text().splitlines():
        if l.startswith('C'):
            tk = l.split()
            u = {'f': 1.0, 'p': 1e3, 'a': 1e-3, 'n': 1e6}.get(tk[3][-1])
            v = float(tk[3][:-1]) * u if u else float(tk[3]) * 1e15
            for n in tk[1:3]:
                tot[n] = tot.get(n, 0.0) + v
    out = {}
    for n in ('Y', 'Z', 'X', 'XTM', 'XTQ', 'APM', 'ANM', 'APQ', 'ANQ', 'EM', 'EQ'):
        out[n] = [round(tot.get(f'XS{k}/{n}', 0.0), 2) for k in range(8)]
    for n in ('BM', 'BQ', 'UP', 'VP'):
        out[n] = [round(tot.get(f'{n}{k}', 0.0), 2) for k in range(8)]
    return out


def _test_rows():
    w = WORK / 'rows'
    w.mkdir(parents=True, exist_ok=True)
    for name, (r, net) in (('t_in', row_in(mux8.P)),):
        r.build()
        print(name, 'width', r.width, 'top', r.top, 'tracks', r.ntracks, 'devices', len(net))
        g = Geo()
        g.place(r.geo)
        ports = sorted(r.track) + ['VDD', 'VSS']
        for i, n in enumerate(ports[:-2]):
            g.label(n, 'metal2', r.ext[n][0] + 0.2, r.track[n], i + 1)
        g.label('VDD', 'metal1', 0.3, r.top - 0.3, len(ports) - 1)
        g.label('VSS', 'metal1', 0.3, 0.3, len(ports))
        (w / f'{name}.tcl').write_text('\n'.join(g.tcl(name)) + '\n')
        magic(w, f'{name}.tcl')
        print(check(w, name, f'.subckt {name} ' + ' '.join(ports) + '\n' + '\n'.join(net) + f'\n.ends {name}\n'))


def check(work, cell, sch_text, sch_cell=None, lvs=True):
    """Magic DRC (full), extraction (LVS netlist + C netlist), GDS; each in its own Magic session (see layout_engine)."""
    work = Path(work)
    drc = ['crashbackups stop', f'load {cell}', 'select top cell', 'expand', 'drc euclidean on', 'drc style drc(full)',
           'drc check', 'drc catchup', 'set f [open drc-count.txt w]', 'puts $f [drc list count total]', 'close $f',
           'set f [open drc-details.txt w]', 'puts $f [drc listall why]', 'close $f', 'quit -noprompt']
    (work / 'drc.tcl').write_text('\n'.join(drc) + '\n')
    for f in ('drc-count.txt', 'drc-details.txt', f'{cell}.lvs.spice', f'{cell}.ext.spice'):
        if (work / f).exists():
            (work / f).unlink()
    magic(work, 'drc.tcl')
    ext = ['crashbackups stop', f'load {cell}', 'select top cell', 'expand', 'extract all', 'ext2spice lvs',
           f'ext2spice -o {cell}.lvs.spice', 'ext2spice default', 'ext2spice hierarchy off', 'ext2spice subcircuit top on', 'ext2spice cthresh 0',
           f'ext2spice -o {cell}.ext.spice', f'gds write {cell}.gds', 'quit -noprompt']
    (work / 'check.tcl').write_text('\n'.join(ext) + '\n')
    magic(work, 'check.tcl')
    raw = (work / 'drc-count.txt').read_text().strip() if (work / 'drc-count.txt').exists() else 'missing'
    res = dict(drc_errors=le.drc_errors(raw))
    if lvs:
        (work / f'{cell}.sch.spice').write_text(sch_text)
        res['lvs'] = netgen(work, f'{cell}.lvs.spice', cell, f'{cell}.sch.spice', sch_cell or cell, out=f'{cell}-lvs.txt')
    return res


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if what == 'rows':
        _test_rows()
    elif what == 'slice':
        build_slice()
    elif what == 'top':
        build_top(neg='neg' in sys.argv, kl='kl' in sys.argv)
    elif what == 'var':      # size-change robustness (scratch only)
        build_top(dict(wb=80.0, wt=40.0, nor=(4, 40), i1=(24, 48), i3=(32, 12), hdr=176.0, tg=(8, 20)), work=WORK / 'var', out=False)
    else:
        build_slice()
        build_top(neg=True, kl=True)
