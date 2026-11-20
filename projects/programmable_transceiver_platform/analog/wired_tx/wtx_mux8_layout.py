"""wtx_mux8 layout generator, revision 3 (8-phase one-hot muxing pre-driver; schematic = wtx_mux8.py).  NOT published.

    python3 wtx_mux8_layout.py            # build, GDS, every check on the GDS read back from disk, C and R + C netlists, report
                                          #   -> scratch/wired_tx/s13/mux3/out and generated/fast/wtx_mux8.{gds,ext.spice,rc.spice,lvs.spice}
    python3 wtx_mux8_layout.py build      # layout + DRC / LVS in the build directory only (seconds)
    python3 wtx_mux8_layout.py em 24.3    # electromigration table for another bank current (mA), no rebuild

Floorplan (bottom = phase / stream edge, top = pad edge); all device sizes from wtx_mux8.P / wtx_mux8.netlist():

    +------ free ------+-- MAIN loads --+-- POST loads --+------ free ------+    loads upside down: RL pair (output head down)
    | L | control rows | slice x 8  (phases in fold order 0 7 1 6 2 5 3 4) | R |   directly above the buses, RCM, PMOS header
    +---+--------------+----------------------------------------------------+---+   with its VDD rail on the top edge

  wtx_mx_slice (one cell, eight identical instances), abutted rows with shared rails:
      stack   MB / MP / MN of both banks in one NMOS strip (shared diffusion VSS-B-S-A-OUT-A-S-B-VSS), gate tracks on
              Metal1 below, the four output buses on Metal5 over / above the fingers (order MAIN_N, MAIN_P, POST_P, POST_N)
      preQ    POST bank pre-driver: I3, I2, TG + keeper, 2 x NOR                             (row flipped)
      preM    MAIN bank pre-driver, + the EXT pull-down of XT; TGM / TGMB / ENMI / EXTM run through
      in      I0 = NAND(PH, RUNI), I0b, I1, stream gates U / V (AOI21); ENM / OVP / OVN / RUNI run through   (flipped)
      gate    POST stream gating (FB, F xor POL, UP / VP) and the run detector's input stage at the PH pin column
              (hysteresis DH1 / DK / DH2, then DA -> XE, DB -> XD)
      trim    NMOS-only strip: 4-bit trim switches and MOS caps on Y                         (flipped; no well, one rail)
    Rows are compiled by XRow (column description and geometry of timing's compact.Row, plus shared tracks, through
    tracks, per-gate channel length, NMOS-only strips, no edge ports); inter-row nets are Metal3 columns over the cells.
    Only ring nets leave a slice sideways: B (to the previous phase's stack), UP / VP (previous phase's POST data): Metal4
    tracks of the SAME length for every phase (two slice pitches); and XE / XD (detector) on 16 Metal4 tracks over the
    trim strip / gate row, all of the same full length, to the pump chains in the control block; trim bits TR k_b on
    32 Metal4 tracks over the gate / in rows (bit b of the slice at position p on track 8 b + p, pitch 0.72 um) from the
    slice's TR b column to the RIGHT edge of the mux: the trim pins are on the right side (Metal4), all other signal
    pins on the bottom edge (Metal3).
  Control block (class Ctl, left): rows aligned with the slice rows; detector (pump switch chains, MOS caps, sense, RUN),
    enable logic, header-gate inverters, off-state pull-downs under the bus ends; the leak devices are four vertical
    diffusion lines under two 50 um poly plates on VDD in the column left of it.
  Right column: the two 100 kohm AVG resistors (guard-ringed ppolyf_u_1k), upper head under a finger of the MAIN bus end.

Output buses (speed-critical; wiring C as revision 2 within 1.5 fF): Metal5 only, 8 um slot pitch.  Every slice draws a
  BCORE stripe (the drain via stacks land on it); the top widens each segment for the current it carries (bus_width:
  static data, <= 80 % of the Metal5 limit), away from the complementary bus.  Drain columns: contact-wide Metal1 plus
  Metal2 UPW on the half of the finger where the current leaves, UPN on the other half; a via stack where the bus crosses
  the finger, else a Metal4 stub.  Bus -> RL: Metal3 || Metal4 strap under the buses above its own, between their drain
  columns (place_clusters searches the cluster positions; MAIN is centred).
Electromigration (85 C: Metal1-4 2.09 mA/um, Metal5 4.5 mA/um, GF180MCU DRM 14.2 as spec/power-delivery.md; 0.58 mA per
  via cut): em_table(report, i_bank); the metal is sized for EM_I mA per bank with static data.
GDS: written by the analog image's Magic (`cif ostyle gdsii`); the digital image's Magic drops the high-resistance marker
  of ppolyf_u_1k.  ppolyf_u_1k PCells keep their guard ring (without it the device is lost on `gds read`).
"""
import json
import re
import math
import shutil
import subprocess
import sys
from pathlib import Path

import wtx_mux8 as mux8
import tools

sys.path.insert(0, str(tools.PROJECT / 'analog/timing'))
import compact  # noqa: E402  (row geometry constants)
import layout_engine as le  # noqa: E402

WORK = tools.SCRATCH / 's13' / 'mux3'
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
    ok = 'match uniquely' in final and 'property errors' not in final.lower() and 'mismatch' not in final.lower()
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

    def __init__(self, name, cols, wn, wp, order=(), through=(), min_width=0.0, min_tracks=0, tracks=None, nonly=False,
                 fixed=None, near=4, high=()):
        self.name, self.cols, self.wn, self.wp = name, cols, wn, wp
        self.high = set(high)        # (fixed mode) nets that must lie above every net they overlap: series nodes of NORs
        self.nonly, self.fixed, self.near = nonly, fixed, near      # NMOS-only strip / pinned track indices / packing margin
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
        if self.fixed is not None:      # pinned nets keep their index; the others take the lowest index free over their span
            a = self._build(None, dict({n: i for i, n in enumerate(a['nets'])}, **{n: v for n, v in self.fixed.items() if n in a['nets']}))
            tidx = {n: v for n, v in self.fixed.items() if n in a['nets']}
            done = list(tidx)
        for n in a['nets']:
            if n in tidx:
                continue
            lo, hi = a['span'][n]
            t = 0
            if self.fixed is not None:
                if n in self.high:
                    t = max([tidx[m] + 1 for m in done if m not in self.through and lo - self.near <= a['span'][m][1]
                             and a['span'][m][0] - self.near <= hi] or [0])
                while any(tidx[m] == t and lo - self.near <= a['span'][m][1] and a['span'][m][0] - self.near <= hi for m in done):
                    t += 1
            else:
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
        if self.nonly:
            top = gap_top
        g.rect('metal1', 0, y_tapn - RAIL_W / 2, width, y_tapn + RAIL_W / 2)
        g.rect('psubdiff', 0.45, y_tapn - 0.25, width - 0.45, y_tapn + 0.25)
        g.rect('psubdiffcont', 0.55, y_tapn - 0.115, width - 0.55, y_tapn + 0.115)
        if not self.nonly:
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


def g_inv(pre, a, y, wn, wp, WN, WP, l=L0):
    """inverter; N and P finger counts independent (N-heavy / P-heavy drivers)."""
    nfn, nfp = nfing(wn, WN), nfing(wp, WP)
    ng = max(nfn, nfp)
    cols, net = [], []
    for j in range(ng + 1):
        hn = j - 1 < nfn and j >= 1 or j < nfn
        hp = j - 1 < nfp and j >= 1 or j < nfp
        cols.append(dict(k='c', n=(('VSS' if j % 2 == 0 else y) if hn else '-'), p=(('VDD' if j % 2 == 0 else y) if hp else '-')))
        if j < ng:
            cols.append(G(a, wn / nfn, wp / nfp, n=j < nfn, p=j < nfp, l=l))
    net += [fet(f'{pre}n{f}', 'n', y, a, 'VSS', wn / nfn, l) for f in range(nfn)]
    net += [fet(f'{pre}p{f}', 'p', y, a, 'VDD', wp / nfp, l) for f in range(nfp)]
    return cols, net


def g_nand2(pre, a, b, y, wn, wp, WN, WP, wpb=None):
    """a next to the output; with more than one finger the series node is contacted and strapped (one net).
    wpb: total PMOS width of input b when it differs from input a's (wp)."""
    wpb = wp if wpb is None else wpb
    nf = max(nfing(wn, WN), nfing(wp, WP))
    while any(abs(round(v / nf * 200) - v / nf * 200) > 1e-6 for v in (wn, wp, wpb)):
        nf += 1
    n, p, pb = wn / nf, wp / nf, wpb / nf
    m = f'{pre}m'
    cols, net = [RAILV], []
    for f in range(nf):
        mid = dict(k='c', n=(m if nf > 1 else None), p=y)
        if f % 2 == 0:
            cols += [G(b, n, pb), mid, G(a, n, p), C(y, 'VDD', same=False)]
        else:
            cols += [G(a, n, p), mid, G(b, n, pb), RAILV]
        net += [fet(f'{pre}na{f}', 'n', y, a, m, n), fet(f'{pre}nb{f}', 'n', m, b, 'VSS', n),
                fet(f'{pre}pa{f}', 'p', y, a, 'VDD', p), fet(f'{pre}pb{f}', 'p', y, b, 'VDD', pb)]
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


# ------------------------------------------------------------------------------------------------ finger strips
def g_nand3(pre, a, b, c, y, wn, wp):
    """one finger; a next to the output, c at VSS."""
    m1, m2 = f'{pre}m', f'{pre}n'
    cols = [RAILV, G(c, wn, wp), dict(k='c', n=None, p=y), G(b, wn, wp), dict(k='c', n=None, p='VDD'), G(a, wn, wp), C(y)]
    net = [fet(f'{pre}na', 'n', y, a, m1, wn), fet(f'{pre}nb', 'n', m1, b, m2, wn), fet(f'{pre}nc', 'n', m2, c, 'VSS', wn)]
    net += [fet(f'{pre}p{i}', 'p', y, g_, 'VDD', wp) for i, g_ in enumerate((a, b, c))]
    return cols, net


def g_aoi21(pre, a1, a2, b, y, wn, wp):
    """y = !(a1 & a2 | b), sizes as wtx_mux8.aoi21 (NMOS a1 / a2: 2 wn, b: wn; PMOS: 2 wp each); two fingers.
    NMOS  VSS -a2- m -a1- y -a1- m -a2- VSS -b- y        PMOS  z -a2- y -a1- z -a1- y -a2- z -b- VDD -b- z
    tracks must satisfy m < a1 < y < z;  a2 and b below z."""
    m, z = f'{pre}m', f'{pre}z'
    c = lambda n, p: dict(k='c', n=n, p=p)
    cols = [c('VSS', z), G(a2, wn, wp), c(m, y), G(a1, wn, wp), c(y, z), G(a1, wn, wp), c(m, y), G(a2, wn, wp), c('VSS', z),
            G(b, wn, wp), c(y, 'VDD'), G(b, None, wp, n=False), c('-', z)]
    net = []
    for f in range(2):
        net += [fet(f'{pre}na1{f}', 'n', y, a1, m, wn), fet(f'{pre}na2{f}', 'n', m, a2, 'VSS', wn),
                fet(f'{pre}pa1{f}', 'p', y, a1, z, wp), fet(f'{pre}pa2{f}', 'p', y, a2, z, wp), fet(f'{pre}pb{f}', 'p', z, b, 'VDD', wp)]
    net.append(fet(f'{pre}nb', 'n', y, b, 'VSS', wn))
    return cols, net


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


BW, BSP = 3.5, 4.5            # Metal5 bus slot: nominal width / spacing (pitch 8 um); drawn width per slice position: bus_width()
BCORE = 2.5                   # part of the slot every slice draws (the drain via stacks land on it)
VSS_M2 = 3.0                  # Metal2 on a stack VSS column reaches this far up the finger
UPN = 0.4                     # ... and on the half of the finger far from where the column leaves
UPW = 0.7                     # Metal2 width on a drain ('up') column
BUS_ORDER = ('MAIN_N', 'MAIN_P', 'POST_P', 'POST_N')       # from the stack upwards
STUB_M = 4
STUB = 0.9                    # Metal4 stub from a drain column to a bus that does not cross the finger
RISER = 0.75                  # half width of an output pin riser (Metal5)
# ---- PH access (WT43, session 16).  x relative to each slice's left edge (= its VSS strap axis, 'neck').  The PH input
# of every slice continues up through the bus band on the block's own wiring to a Metal4 window pad above the buses;
# the chip's ring router lands on it from the top edge with a Metal5 lane (Via4).  In the bus band PH runs on Metal3
# under a VSS Metal4 shield with VSS Metal3 on both sides (no output bus sees PH).
PH_A = (0.65, 1.05)           # Metal3 from the slice PH pin (pin x + this) up to below the stack VSS rail
PH_J = (4.65, 5.05)           # Metal4 jog past the stack VSS rail (rail Metal ends at 4.3; another net's Metal3 at 5.0)
PH_C = (3.87, 4.27)           # Metal3 through the bus band
SH4 = (3.05, 5.10)            # VSS Metal4 shield over PH_C (0.34 / 0.33 to the MAIN_N stack and MAIN_P stub Metal4)
SH3 = ((3.05, 3.45), (4.57, 4.97))   # VSS Metal3 beside PH_C
WIN = (4.05, 5.65)            # Metal4 window pad (PH), above POST_N
LANE = (4.45, 5.25)           # the ring's Metal5 lane onto the window (kept Metal5-free here, 0.6 each side)
STRAP_KEEP = (2.75, 6.65)     # tap straps (Metal3 || Metal4) stay out of the shield / window guard
# ---- grid VSS ties (ASM-8): VSS Metal3 || Metal4 verticals in the neck zones (between the previous slice's last drain
# column and this slice's MAIN_N stack) from the stack VSS rail up to above the buses, Via4 onto a Metal5 pad there;
# the block joins each pad to a grid VSS landing (16 um at the grid axes, block x 23.5 + 35 k = mux x GRID_AX0 + 35 k).
VZONE = (-4.2, 1.4)           # neck zone, within the stack VSS rail (neck 0: from -3.0, control-block stubs at -4.59 / -3.69)
GRID_AX0, LAND_HW = 26.4, 8.0
TIE_N3 = 2.8                  # Metal3 width of a tie vertical inside the POST_N band (pair C balance; EM in the IR raster)



class Strip2(Strip):
    """revision-2 strips: drain Metal2 only over the finger, VSS Metal2 only to the finger top (the two end columns
    still reach the top tap rail), 0.4 um Metal1 on internal-node columns."""

    def build(self):
        super().build()
        if self.gate_bar:
            return self
        g, yd0, up_to = self.geo, self.yd0, self.top
        ybar = yd0 + self.wmax + 0.3
        self.upw = min(UPW, self.m2w)
        ends = (self.x[0], self.x[-1])
        out = []
        for layer, x1, y1, x2, y2 in g.r:
            xm = s((x1 + x2) / 2)
            i = self.x.index(xm) if xm in self.x else None
            c = self.cols[i] if i is not None else None
            role = self.roles.get(c[1]) if c and c[0] == 'c' else None
            if layer == 'metal2' and role == 'up' and abs(y2 - s(up_to)) < 1e-6 and abs(y1 - yd0) < 1e-6:
                # full width on the half where the column leaves (bus stack at the foot: 'lo', else at the finger top),
                # UPN on the other half (it carries at most half of the column current)
                ym, nw = s(yd0 + self.w[i] / 2), min(UPN, self.upw)
                lo = getattr(self, 'exit', {}).get(c[1]) == 'lo'
                out.append((layer, s(xm - (self.upw if lo else nw) / 2), y1, s(xm + (self.upw if lo else nw) / 2), ym))
                out.append((layer, s(xm - (nw if lo else self.upw) / 2), ym, s(xm + (nw if lo else self.upw) / 2), s(yd0 + self.w[i])))
            elif role == 'down' and xm not in ends and self.top_rail and layer == 'metal2' and abs(y2 - s(up_to - 0.3)) < 1e-6:
                out.append((layer, x1, y1, x2, s(yd0 + self.w[i])))
            elif role == 'down' and xm not in ends and self.top_rail and layer == 'via1' and y1 > yd0 + self.wmax:
                pass
            elif layer == 'metal1' and role == 'bar' and abs(y2 - s(ybar + BAR_H)) < 1e-6 and abs(x2 - x1 - 0.6) < 1e-6:
                out.append((layer, s(xm - CW / 2), y1, s(xm + CW / 2), y2))      # contact-wide Metal1 (less facing the drains)
            elif role == 'up' and layer in ('metal1', 'via1') and abs(y1 - yd0) < 0.11 and x2 - x1 < 0.45:
                # drain column: contact-wide Metal1, Via1 (with 0.38 um Metal1 pads) in three short groups
                if layer == 'metal1':
                    out.append((layer, s(xm - CW / 2), y1, s(xm + CW / 2), y2))
                else:
                    wi = self.w[i]
                    for f in ((1, 3, 5) if wi >= 6 else (1, 5) if wi >= 3.2 else (3,)):
                        yc = yd0 + wi * f / 6
                        out.append(('metal1', s(xm - 0.19), s(yc - 0.7), s(xm + 0.19), s(yc + 0.7)))
                        out.append(('via1', s(xm - 0.13), s(yc - 0.6), s(xm + 0.13), s(yc + 0.6)))
            elif role == 'down' and layer == 'metal2' and abs(x2 - x1 - 1.1) < 1e-6 and xm not in ends:
                out.append((layer, s(xm - 0.4), y1, s(xm + 0.4), s(yd0 + min(VSS_M2, self.w[i]))))        # VSS Metal2 0.8 um, only to the finger foot
            elif role == 'down' and layer == 'via1' and abs(y1 - yd0 - 0.1) < 1e-6 and xm not in ends and x2 - x1 < 0.3:
                out.append((layer, x1, y1, x2, s(yd0 + min(VSS_M2, self.w[i]) - 0.1)))                          # (Metal1 0.4 um carries the column)
            else:
                out.append((layer, x1, y1, x2, y2))
        g.r = out
        return self


def stack2(P, min_width=0.0, bw=BW):
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
    st = Strip2('n', cols, gt, roles, min_width=min_width, top_rail=True)
    st.build()
    st.up_to = s(st.yd0 + 0.3 + 4 * bw + 3 * BSP + 0.3)
    st.build()
    st.bw = bw
    st.bus = {n: s(st.yd0 + 0.3 + i * (bw + BSP)) for i, n in enumerate(BUS_ORDER)}
    st.exit = {n: 'lo' for n, yb in st.bus.items() if min(yb + BCORE, st.yd0 + wtf) - yb >= 1.5}      # as bus_vias2 decides
    st.build()
    st.nfb = nfb
    return st, st.devices('mk')


def bus_vias2(self, key):
    """drain columns -> Metal5 bus: via stack where the bus crosses the finger, else a Metal3 || Metal4 stub."""
    st, x0, y0 = self.strips[key]
    for n, yb in self.bus.items():
        for xx in st.col_x.get(n, []):
            i = st.x.index(xx)
            ydt, b0, b1, xc, h = y0 + st.yd0 + st.w[i], y0 + yb, y0 + yb + getattr(self, 'bcore', BCORE), x0 + xx, st.upw / 2
            if min(b1, ydt) - b0 >= 1.5:
                self.g.varr(xc - h, b0 + 0.1, xc + h, min(b1, ydt) - 0.1, 2, 5)
            else:
                ya = max(y0 + st.yd0 + 0.1, ydt - 2.7)
                self.g.varr(xc - h, ya, xc + h, ydt - 0.1, 2, 4)
                self.g.rect(f'metal{STUB_M}', xc - STUB / 2, ya, xc + STUB / 2, b1 - 0.1)       # stub on one layer
                if STUB_M == 3:
                    self.g.varr(xc - STUB / 2, b0 + 0.1, xc + STUB / 2, b1 - 0.1, 3, 4)
                self.g.varr(xc - STUB / 2, b0 + 0.1, xc + STUB / 2, b1 - 0.1, 4, 5)




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


Block.bus_vias = bus_vias2


VSS_W, VDD_W = 9.0, 5.0      # Metal5 strap widths (VSS on the slice boundaries, VDD inside every slice)
VSS_S, VDD_S = 1.5, 2.0      # half width of the via stacks on the logic rails
OUT_S = 5.4                  # half width of an output Metal5 strap (0.6 um to the header VDD straps, MT.2b)


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



# ------------------------------------------------------------------------------------------------ slice rows (revision 3)
NTR = mux8.NTR
XP = 0.84                     # pitch of the detector's XE / XD Metal4 tracks
TRP = 0.72                    # pitch of the trim Metal4 tracks (Metal4 0.4 wide, 0.32 apart)
TRIM_WN = 6.0                 # finger width limit of the trim strip (4.0 does not fit the slice width)


def row_trim(P, min_width=0.0):
    """NMOS-only strip under the gate row: trim switches Y -> YC b (wts 2^b) and MOS caps (ctrim[0] 2^b, l = ctrim[1])."""
    WN = TRIM_WN
    (wc, lc), ws = P['ctrim'], P['wts']
    cn = lambda n: dict(k='c', n=n, p='-')

    def sw(b, rev=False):
        w = ws * 2 ** b
        nf = nfing(w, WN)
        c = [cn(f'YC{b}')]
        for f in range(nf):
            c += [G(f'TR{b}', w / nf, p=False), cn('Y' if f % 2 == 0 else f'YC{b}')]
        return (c[::-1] if rev else c), [fet(f'ts{b}_{f}', 'n', 'Y', f'TR{b}', f'YC{b}', w / nf) for f in range(nf)]

    def cap(b):
        w = wc * 2 ** b
        nf = nfing(w, WN)
        c = [cn('VSS')]
        for f in range(nf):
            c += [G(f'YC{b}', w / nf, p=False, l=lc), cn('VSS')]
        return c, [fet(f'tc{b}_{f}', 'n', 'VSS', f'YC{b}', 'VSS', w / nf, lc) for f in range(nf)]
    if NTR != 4:
        raise ValueError('row_trim is written for four trim bits')
    cols, net = [], []
    for c, n in (cap(0), sw(0), sw(1, True), cap(1), cap(2), sw(2), sw(3), cap(3)):
        join(cols, c)
        net += n
    tr = dict(Y=0, YC0=1, YC1=1, YC2=1, YC3=1, TR0=2, TR1=3, TR2=2, TR3=3)
    return XRow('trim', cols, WN, WN, min_width=min_width, tracks=tr, nonly=True), net


def row_gate(P, min_width=0.0):
    """static stream gating of the POST bank (FB, FP = F xor POL, UP / VP) and the run detector's two inverters on PH."""
    gw = P['gate']
    WN, WP = gw
    cols, net = [], []
    # at the left end, under I0 (one short PH column): run detector input stage with hysteresis DH1 PH -> XH, keeper
    # DK XS -> XH, DH2 XH -> XS, then DA XS -> XE, DB XE -> XD
    # (single-finger inverters; every second one mirrored so that neighbours share an output or a rail contact)
    h1, hk, h2 = P['det']['hys']
    for pre, a, y, sz, rev in (('dh1', 'PH', 'XH', h1, 0), ('dk', 'XS', 'XH', hk, 1), ('dh2', 'XH', 'XS', h2, 0),
                               ('da', 'XS', 'XE', P['det']['buf'], 1), ('db', 'XE', 'XD', P['det']['buf'], 0)):
        c, n = g_inv(pre, a, y, sz[0], sz[1], WN, WP, *sz[2:])
        join(cols, c[::-1] if rev else c)
        net += n
    for kind, pre, *pins in (('i', 'gf', 'F', 'FB'), ('n', 'gx1', 'F', 'POLB', 'N1'), ('n', 'gx2', 'FB', 'POL', 'N2'),
                             ('n', 'gx3', 'N1', 'N2', 'FP'), ('i', 'gx4', 'FP', 'FPB'),
                             ('n', 'gp', 'FP', 'ENP', 'UPO'), ('n', 'gq', 'FPB', 'ENP', 'VPO')):
        c, n = (g_inv if kind == 'i' else g_nand2)(pre, *pins, *gw, WN, WP)
        join(cols, c)
        net += n
    tr = dict(F=0, UPO=0, VPO=0, FB=1, FPB=1, N1=2, N2=3, FP=3, ENP=4, POL=5, POLB=6, PH=3, XH=0, XS=1, XE=2, XD=3)
    return XRow('gate', cols, WN, WP, through=['ENP', 'POL', 'POLB'], min_width=min_width, tracks=tr), net


def row_in(P, min_width=0.0):
    """phase input chain I0 (NAND PH, RUNI), I0b, I1 and the MAIN stream gates U / V (AOI21)."""
    WN, WP = 4.0, 8.0
    if P['gdrv'][0] > WN or P['gdrv'][1] > WP:
        raise ValueError('gdrv finger wider than the row')
    cols, net = [], []
    c, n = g_nand2('i0', 'PH', 'RUNI', 'Y', P['i0'][0], P['i0'][1], WN, WP, wpb=P['i0x'])
    join(cols, c)
    net += n
    if not any(l.split()[0] == 'Xi0na1' for l in n):
        raise ValueError('row_in: I0 must have two fingers (track plan)')
    for pre, a, y, key in (('i0b', 'Y', 'Z', 'i0b'), ('i1', 'Z', 'X', 'i1')):
        c, n = g_inv(pre, a, y, *P[key], WN, WP)
        join(cols, c)
        net += n
    for pre, a1, b, y in (('gu', 'F', 'OVP', 'UO'), ('gv', 'FB', 'OVN', 'VO')):
        c, n = g_aoi21(pre, a1, 'ENM', b, y, *P['gdrv'])
        join(cols, c)
        net += n
    tr = dict(ENM=0, OVP=1, OVN=2, RUNI=3, i0m=4, gum=4, gvm=4, PH=5, X=5, F=5, FB=5, Y=6, UO=6, VO=6, Z=7, guz=7, gvz=7)
    return XRow('in', cols, WN, WP, through=['ENM', 'OVP', 'OVN', 'RUNI'], min_width=min_width, tracks=tr), net


def row_pre(P, tag, min_width=0.0):
    """pre-driver of one bank: I3, I2 (NAND), TG + keeper (+ the EXT pull-down of XT in the MAIN bank), the two NORs."""
    WN, WP = 8.0, 12.0
    t = tag
    en, tgn, tgp, u, v, ex = ('ENMI', 'TGM', 'TGMB', 'UO', 'VO', 'EXTM') if t == 'M' else ('ENQI', 'ENQI', 'ENQIB', 'UPI', 'VPI', None)
    xt, ap, an, e, bo = f'XT{t}', f'AP{t}', f'AN{t}', f'E{t}', f'B{t}O'
    cols, net = [], []
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
        tg += [dict(k='c', n=('X' if f % 2 == 0 else xt), p='-'), G(tgn, wtn / nfn, p=False)]
        net.append(fet(f'tgn{t}{f}', 'n', xt, tgn, 'X', wtn / nfn))
    last = xt if nfn % 2 else 'X'
    if ex:
        if last != xt:
            raise ValueError('row_pre: the NMOS TG chain must end on XT')
        tg += [dict(k='c', n=xt, p='-'), G(ex, 2.0, p=False)]
        net.append(fet(f'tgx{t}', 'n', xt, ex, 'VSS', 2.0))
        last = 'VSS'
    first = xt if nfp % 2 == 0 else 'X'          # the P chain ends on XT, where the keeper attaches
    tg.append(dict(k='c', n=last, p=first))      # one column: end of the NMOS island, start of the PMOS island
    for f in range(nfp):
        tg += [G(tgp, None, wtp / nfp, n=False), dict(k='c', n='-', p=(('X' if first == xt else xt) if f % 2 == 0 else first))]
        net.append(fet(f'tgp{t}{f}', 'p', xt, tgp, 'X', wtp / nfp))
    tg += [G(en, None, 1.0, n=False), dict(k='c', n='-', p='VDD')]
    net.append(fet(f'tgk{t}', 'p', xt, en, 'VDD', 1.0))
    join(cols, tg)
    for pre, b_, y in ((f'np{t}', u, ap), (f'nn{t}', v, an)):
        c, n = g_nor2(pre, xt, b_, y, *P['nor'], WN, WP)
        join(cols, c)
        net += n
    tr = {tgp: 0, 'X': 1, xt: 2, ap: 3, an: 3, e: 3, u: 4, v: 4, bo: 4, f'np{t}m': 5, f'nn{t}m': 5, tgn: 6}
    thr = [tgn, tgp]
    if t == 'M':
        tr.update(ENMI=7, EXTM=8)
        thr += ['ENMI', 'EXTM']
    return XRow('pre' + t, cols, WN, WP, through=thr, min_width=min_width, tracks=tr), net


# ------------------------------------------------------------------------------------------------ phase slice
ROWS = ('trim', 'gate', 'in', 'preM', 'preQ')
FLIP = (True, False, True, False, True)


class RBlock(Block):
    def rail_m2(self):
        """Metal2 over every logic rail (rows have Metal1 rails only); an NMOS-only strip has one rail."""
        for r, y0, flip in self.rows.values():
            ys_ = (y0, y0 + r.top - RAIL_W)
            if r.nonly:
                ys_ = ys_[1:] if flip else ys_[:1]
            for yr in ys_:
                self.g.rect('metal2', 0, yr, self.W, yr + RAIL_W)
                self.g.rect('via1', 0.3, yr + 0.1, self.W - 0.3, yr + RAIL_W - 0.1)


class Slice(RBlock):
    def __init__(self, P):
        err = None
        for vx in (10.5, 9.5, 11.5, 8.5, 12.5, 7.5, 13.5, 6.0, 14.5, 16.0, 18.0, 20.0, 22.0, 24.0):     # Metal5 VDD strap position
            try:
                self.vdd_x = vx
                self.make(P)
                return
            except RuntimeError as e:
                err = e
        raise err

    def make(self, P):
        mk = lambda W=0.0: [row_trim(P, W), row_gate(P, W), row_in(P, W), row_pre(P, 'M', W), row_pre(P, 'Q', W)]
        st, nst = stack2(P)
        self.W = W = s(math.ceil(max([st.width] + [r.build().width for r, _ in mk()]) * 2) / 2)
        st, nst = stack2(P, W)
        rows = mk(W)
        self.net = nst + [l for _, n in rows for l in n]
        self.ys = ys = self.setup([r for r, _ in rows], FLIP)
        self.st, self.bus, self.bw = st, st.bus, st.bw
        self.strips['stack'] = (st, 0.0, ys)
        self.H = s(ys + st.top + 0.3)
        for xb in (0.0, W):
            self.excl += [(xb - VSS_S - 0.3, xb + VSS_S + 0.3, 0, self.H), (xb - VSS_W / 2 + 0.1, xb + VSS_W / 2 - 0.1, ys - 0.1, ys + st.rail_h + 0.1)]
        self.excl.append((self.vdd_x - VDD_S - 0.3, self.vdd_x + VDD_S + 0.3, 0, ys - 1.0))
        for n, v in st.col_x.items():            # Metal3 keeps clear of the drain columns' stacks / stubs in the bus band
            if st.roles[n] == 'up':
                self.excl += [(xx - STUB / 2 - 0.1, xx + STUB / 2 + 0.1, ys + st.yd0 - 0.2, self.H) for xx in v]
        yq, ym, yg = self.rows['preQ'][1], self.rows['preM'][1], self.rows['gate'][1]
        self.ring_y = {'BM': s(yq + 5.0), 'BQ': s(yq + 5.0 + 4 * RT_P['BM']), 'UP': s(ym + 12.0), 'VP': s(ym + 12.0 + 4 * RT_P['UP'])}
        # detector tracks (Metal4, drawn by the top over the trim strip / gate row): XE below the shared VSS rail, XD above it
        self.det_y = {'XE': s(yg - 0.5 - 7 * XP), 'XD': s(yg + RAIL_W + 1.1)}
        if self.det_y['XE'] < 0.6:
            raise ValueError('no room for the XE tracks over the trim strip')
        # trim tracks (Metal4, drawn by the top over the gate / in rows): bit b of the slice at position p on
        # tr_ys[8 b + p], from the slice's TR b column to the right edge of the mux (trim pins on the right side)
        # (pitch TRP; clear of the Metal2-5 VDD via stacks on the in row's rail and below the stacks on the preM VSS rail)
        y_in, y_pm = self.rows['in'][1], self.rows['preM'][1]
        lo_bad, hi_bad = y_in + 0.05 - 0.28 - 0.2, y_in + 0.55 + 0.28 + 0.2
        ys_, y = [], s(self.det_y['XD'] + 7 * XP + 1.2)
        while len(ys_) < 32:
            if y + 0.2 > y_pm + 0.05 - 0.28:
                raise ValueError('no room for the 32 trim tracks below the preM VSS rail stacks')
            if not (lo_bad < y < hi_bad):
                ys_.append(s(y))
            y += TRP
        self.tr_ys = ys_
        self.tr_y0 = ys_[0]
        self.route()
        self.finish()
        self.rail_m2()
        for n, yb in st.bus.items():
            self.g.rect('metal5', 0, ys + yb, W, ys + yb + BCORE)
        self.bus_vias('stack')
        for row, nets in (('in', ('Y', 'Z', 'X')), ('preM', ('XTM', 'APM', 'ANM', 'EM')), ('preQ', ('XTQ', 'APQ', 'ANQ', 'EQ')),
                          ('gate', ('XE', 'XD', 'FB'))):
            for n in nets:
                self.g.label(n, 'metal2', self.rows[row][0].ext[n][0] + 0.2, self.ty(row, n))
        for n in ('SM', 'SQ'):
            self.g.label(n, 'metal1', st.col_x[n][0], ys + st.yd0 + 1.0)

    def route(self):
        ry = self.ring_y
        grp = lambda n: (ry[n], s(ry[n] + 3 * RT_P[n]))
        det = lambda n: (self.det_y[n], s(self.det_y[n] + 7 * XP))
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
        c('PH', [('gate', 'PH'), ('in', 'PH')], (0.2,))
        c('Y', [('trim', 'Y'), ('in', 'Y')])
        c('UO', [('in', 'UO'), ('preM', 'UO')])
        c('VO', [('in', 'VO'), ('preM', 'VO')])
        c('UPO', [('gate', 'UPO')], grp('UP'))
        c('VPO', [('gate', 'VPO')], grp('VP'))
        c('UPI', [('preQ', 'UPI')], grp('UP'))
        c('VPI', [('preQ', 'VPI')], grp('VP'))
        c('F', [('gate', 'F'), ('in', 'F')], (0.2,))
        c('FB', [('gate', 'FB'), ('in', 'FB')])
        c('XE', [('gate', 'XE')], det('XE'))
        c('XD', [('gate', 'XD')], det('XD'))
        for b in range(NTR):
            c(f'TR{b}', [('trim', f'TR{b}')], (self.tr_ys[8 * b], self.tr_ys[8 * b + 7]))


# ------------------------------------------------------------------------------------------------ resistor PCells
def gen_res(work, specs):
    """ppolyf_u PCells WITHOUT guard ring (the ring's PPLUS sits 0.27 um from the resistor's: KLayout PP.2; same choice
    as rf_tx/layoutlib.py); the substrate terminal is tied to VSS by tap strips beside them.
    specs: {cell name: (model, w, l)}.  Returns the head geometry of each cell (vertical resistor, centred)."""
    cmds = ['crashbackups stop', 'load primitive_workspace']
    for name, (model, w, l) in specs.items():
        # ppolyf_u_1k keeps its guard ring (as layout_engine): without it the device is lost when the GDS is read back and
        # KLayout flags PP.9 / PRES.1 / PRES.5
        gr = 1 if model == 'ppolyf_u_1k' else 0
        cmds += ['units internal', f'set cell [magic::gencell_makecell gf180mcu::{model} w {w} l {l} guard {gr} full_metal {gr}]',
                 'load $cell', f'save {name}', 'load primitive_workspace']
    (work / 'prim.tcl').write_text('\n'.join(cmds + ['quit -noprompt']) + '\n')
    magic(work, 'prim.tcl')
    out = {}
    for name in specs:
        r = le.rects(work / f'{name}.mag')
        pc = sorted(r['polycontact'], key=lambda a: a[1])
        res = [k for k in r if 'res' in k]
        out[name] = dict(hx=pc[0][2], c0=(pc[0][1], pc[0][3]), c1=(pc[-1][1], pc[-1][3]),
                         py=max(a[3] for a in r['polysilicon']), body=max(a[3] for k in res for a in r[k]),
                         bx=max(a[2] for k in r for a in r[k]), layers=sorted(r))
    return out


# ------------------------------------------------------------------------------------------------ control block (left end)
LEAK_W = 4.8                 # width of the leak-device column left of the control rows
PD_W = 10.5                  # the two off-state pull-down strips (right end of the block, under the buses)


def sch_w(P):
    """total width (um) of every schematic transistor (fingers summed), from wtx_mux8.netlist()."""
    d = {}
    for l in mux8.netlist(P).splitlines():
        if l.startswith('X') and 'fet_03v3' in l:
            name = l.split()[0][1:].rsplit('_', 1)[0]
            d[name] = round(d.get(name, 0.0) + float(re.search(r' w=([\d.]+)u', l).group(1)), 4)
    return d


class Ctl(RBlock):
    """left end block, rows aligned with the slice rows (the static controls leave on the slices' through tracks):
      trim strip   detector MOS caps CN j / CA j
      gate row     the four pump switch chains (series PMOS; gates XE / XD arrive on the Metal4 detector tracks)
      in row       sense inverters, RUN logic, POLB
      preM row     EXTB, EXTF, RUNI (= RUN, from RUNB), RXB, ENM0
      preQ row     bank enables ENMI / ENQI / ENQIB, TGM / TGMB, EXTM, header-gate inverters ENBM / ENBQ
      above        off-state pull-downs of the four outputs under the bus ends
      left column  the leak devices (nleak x 0.3 / 50 um in series per pump, vertical, common poly plates on VDD).
    Gate sizes come from the schematic netlist (sch_w); the gate list mirrors wtx_mux8.netlist() and LVS checks it."""

    def __init__(self, P, sl, W=None):
        err = None
        for w in ([W] if W else [28.0, 30.0, 32.0, 34.0, 36.0, 40.0]):
            try:
                self.make(P, sl, w)
                return
            except (RuntimeError, ValueError) as e:
                err = e
        raise err

    def make(self, P, sl, W):
        self.W, self.net = W, []
        D, d, ref = P['det'], sch_w(P), sl.rows
        mrank = lambda n: 3 if (n[0].islower() and n.endswith('m')) else 2 if n[:2] in ('DA', 'DN') else 0 if n[:2] in ('XE', 'XD') else 1

        def row(name, groups, WN, WP, tracks=None):
            cols = []
            for c, n in groups:
                join(cols, c)
                self.net += n
            rr = ref[name][0]
            seen = []
            for c in cols:
                for n in ([c.get('n'), c.get('p')] if c['k'] == 'c' else [c['net']]):
                    if n and n not in ('-', 'VSS', 'VDD') and n not in seen:
                        seen.append(n)
            kw = dict(tracks=tracks) if tracks else dict(fixed={n: rr.tracks[n] for n in rr.through}, near=2,
                                                         order=sorted(seen, key=mrank),
                                                         high=[n for n in seen if mrank(n) == 3])
            r = XRow(name, cols or [BRK], WN, WP, through=list(rr.through), min_width=W, min_tracks=rr.ntracks, nonly=rr.nonly, **kw)
            r.build()
            if r.ntracks != rr.ntracks:
                raise ValueError(f'control row {name} needs {r.ntracks} tracks, the slice row has {rr.ntracks}')
            return r
        I = lambda pre, a, y, WN, WP, l=L0: g_inv(pre.lower(), a, y, d[pre + 'n'], d[pre + 'p'], WN, WP, l)
        ND = lambda pre, a, b, y, WN, WP: g_nand2(pre.lower(), a, b, y, d[pre + 'na'], d[pre + 'pa'], WN, WP)
        NR = lambda pre, a, b, y, WN, WP: g_nor2(pre.lower(), a, b, y, d[pre + 'na'], d[pre + 'pa'], WN, WP)
        # ---- trim strip: detector caps (gate = node, source = drain = VSS)
        cn = lambda n: dict(k='c', n=n, p='-')
        capc, capn = [cn('VSS')], []
        for j in range(4):                   # CN j, CA j: DN j (track j) comes from the left edge, DA j (track j) lies right of it
            for key, node in (('cn', 'DN'), ('ca', 'DA')):
                w, l = D[key]
                nf = nfing(w, TRIM_WN)
                for f in range(nf):
                    capc += [G(f'{node}{j}', w / nf, p=False, l=l), cn('VSS')]
                    capn.append(fet(f'dc{node}{j}_{f}', 'n', 'VSS', f'{node}{j}', 'VSS', w / nf, l))
        ttr = {f'{node}{j}': j for node in ('DN', 'DA') for j in range(4)}
        # ---- gate row: pump switch chains  VDD -XE a- . -XD b- DA j -XE b- . -XD c- DN j
        quads = []
        pc = lambda p: dict(k='c', n='-', p=p)
        gp = lambda n: G(n, None, D['sw'], n=False)
        for j in range(4):
            a, b, c_ = 2 * j, 2 * j + 1, (2 * j + 2) % 8
            quads.append(([pc(f'DN{j}'), gp(f'XD{c_}'), pc(None), gp(f'XE{b}'), pc(f'DA{j}'), gp(f'XD{b}'), pc(None), gp(f'XE{a}'), pc('VDD')],
                          [fet(f'dp1{j}', 'p', f'dm1{j}', f'XE{a}', 'VDD', D['sw']), fet(f'dp2{j}', 'p', f'DA{j}', f'XD{b}', f'dm1{j}', D['sw']),
                           fet(f'dp3{j}', 'p', f'dm2{j}', f'XE{b}', f'DA{j}', D['sw']), fet(f'dp4{j}', 'p', f'DN{j}', f'XD{c_}', f'dm2{j}', D['sw'])]))
        gw = P['gate']
        sense = [g_inv(f'ds{j}', f'DN{j}', f'DRB{j}', D['sense'][0], D['sense'][1], 4.0, 8.0, D['sl']) for j in range(4)]
        rtrim = row('trim', [(capc, capn)], TRIM_WN, TRIM_WN, tracks=ttr)
        # every chain sits over its caps: the DN column (chain's left end) lands left of the DN j cap contact, the DA column right of it
        nb, net0 = [0, 0, 0, 0], list(self.net)
        for _ in range(200):
            self.net = list(net0)
            rgate = row('gate', [([BRK] * nb[j] + qc if nb[j] else qc, qn) for j, (qc, qn) in enumerate(quads)], *gw)
            xdn = {c['p']: rgate.x[i] for i, c in enumerate(rgate.cols) if c['k'] == 'c' and str(c.get('p'))[:2] == 'DN'}
            bad = [j for j in range(4) if xdn[f'DN{j}'] < rtrim.ext[f'DN{j}'][1] - 0.2 - 0.66]
            if not bad:
                break
            nb[bad[0]] += 1
        if any(xdn[f'DN{j}'] > rtrim.ext[f'DN{j}'][1] - 0.2 for j in range(4)):
            raise ValueError('pump chain cannot be aligned with its caps')
        rows = [rtrim, rgate,
                row('in', [sense[0], NR('DR01', 'DRB0', 'DRB1', 'DR01', 4.0, 8.0), sense[1],
                           ND('DRN', 'DR01', 'DR23', 'RUNB', 4.0, 8.0), I('DRI', 'RUNB', 'RUN', 4.0, 8.0), sense[2],
                           NR('DR23', 'DRB2', 'DRB3', 'DR23', 4.0, 8.0), sense[3], I('IPOL', 'POL', 'POLB', 4.0, 8.0)], 4.0, 8.0),      # order: four free tracks only
                row('preM', [I('IEXT', 'EXT', 'EXTB', 8.0, 12.0), NR('GXF', 'EXTB', 'RUN', 'EXTF', 8.0, 12.0), I('GXFI', 'RUNB', 'RUNI', 8.0, 12.0),
                             NR('GRE', 'RUN', 'EXT', 'RXB', 8.0, 12.0), I('GEMI', 'EN_MAIN', 'ENMAINB', 8.0, 12.0),
                             NR('GEM', 'RXB', 'ENMAINB', 'ENM0', 8.0, 12.0)], 8.0, 12.0),
                row('preQ', [I('IEM', 'ENMI', 'ENBM', 8.0, 12.0), I('IEQ', 'ENQI', 'ENBQ', 8.0, 12.0),
                             I('GEM2', 'ENM0', 'ENMIB', 8.0, 12.0), I('GEM3', 'ENMIB', 'ENMI', 8.0, 12.0),
                             ND('GTG', 'ENMI', 'RUNI', 'TGMB', 8.0, 12.0), I('GTGI', 'TGMB', 'TGM', 8.0, 12.0),
                             ND('GXM', 'ENMI', 'EXTF', 'EXTMB', 8.0, 12.0), I('GXMI', 'EXTMB', 'EXTM', 8.0, 12.0),
                             g_nand3('geq', 'EN_POST', 'RUN', 'EXTB', 'ENQN', d['GEQa'], d['GEQd']), I('GEQ2', 'ENQN', 'ENQI', 8.0, 12.0),
                             I('GQB', 'ENQI', 'ENQIB', 8.0, 12.0)], 8.0, 12.0)]
        ys = self.setup(rows, FLIP)
        for r, y0, _ in self.rows.values():
            if abs(r.top - ref[r.name][0].top) > 1e-6 or abs(y0 - ref[r.name][1]) > 1e-6:
                raise RuntimeError(f'control row {r.name} does not line up with the slice rows')
        st = sl.st
        self.bus, self.bw, self.ys, self.H = sl.bus, sl.bw, ys, sl.H
        nt = max(st.gt.values())
        for key, enb, op, on, x0, mw in (('pdM', 'ENBM', 'MAIN_P', 'MAIN_N', W - PD_W, 4.0), ('pdQ', 'ENBQ', 'POST_P', 'POST_N', W - PD_W + 4.0, PD_W - 4.0)):
            pd = Strip2('n', [('c', op), ('g', enb, P['pd']), ('c', 'VSS'), ('g', enb, P['pd']), ('c', on)], {enb: nt},
                        {op: 'up', on: 'up', 'VSS': 'down'}, rail_h=st.rail_h, m2w=0.5, up_to=st.up_to, top_rail=True, min_width=mw)
            pd.build()
            if abs(pd.yd0 - st.yd0) > 1e-6:
                raise RuntimeError('pull-down strip does not line up with the stack')
            self.strips[key] = (pd, x0, ys)
            self.net += pd.devices(key)
        self.excl += [(W - VSS_S - 0.3, W + VSS_S + 0.3, 0, self.H), (W - VSS_W / 2 + 0.1, W + VSS_W / 2, ys - 0.1, ys + st.rail_h + 0.1)]
        self.excl.append((W - PD_W - 0.6, W, ys + st.yd0 - 0.2, self.H))      # no foreign Metal3 beside the pull-downs' drain stacks
        c = self.column
        det = sl.det_y
        jog = [0]

        def link(name, ta, tb):
            """two terminals: one Metal3 column, or (no common x) two columns joined by a Metal4 jog over the preM row."""
            n0, r0, e0 = len(self.cols3), len(self.g.r), {k: dict(v[0].ext) for k, v in self.rows.items()}
            try:
                return c(name, [ta, tb])
            except RuntimeError:
                pass
            yj = s(self.rows['preM'][1] + 3.0 + 0.8 * jog[0])
            jog[0] += 1
            c(name + '_a', [ta], (yj,))
            c(name + '_b', [tb], (yj,))
            xa, xb = self.pin[name + '_a'][0], self.pin[name + '_b'][0]
            if max(xa, xb) > W - VSS_S - 1.0:
                raise RuntimeError(f'jog of {name} reaches the power stacks')
            self.g.rect('metal4', min(xa, xb) - 0.2, yj - 0.2, max(xa, xb) + 0.2, yj + 0.2)
            self.g.via(xa, yj, 3, 4)
            self.g.via(xb, yj, 3, 4)

        def pin(name, term):
            """input pin at the bottom edge: one column from the terminal down, or a free column joined by a Metal4 jog."""
            try:
                return c(name, [term], (0.2,))
            except RuntimeError:
                pass
            yj = s(self.rows['preM'][1] + 3.0 + 0.8 * jog[0])
            jog[0] += 1
            c(name + '_a', [term], (yj,))
            c(name, [], (0.2, yj))
            xa, xb = self.pin[name + '_a'][0], self.pin[name][0]
            if max(xa, xb) > W - VSS_S - 1.0:
                raise RuntimeError(f'jog of {name} reaches the power stacks')
            self.g.rect('metal4', min(xa, xb) - 0.2, yj - 0.2, max(xa, xb) + 0.2, yj + 0.2)
            self.g.via(xa, yj, 3, 4)
            self.g.via(xb, yj, 3, 4)
        self.feed_y = {'ENBM': s(self.H + 1.4), 'ENBQ': s(self.H + 0.6)}      # the MAIN header pad is the left one: its riser must not cross the POST feed
        for j in range(4):
            c(f'DN{j}', [('gate', f'DN{j}'), ('trim', f'DN{j}')])
            c(f'DA{j}', [('gate', f'DA{j}'), ('trim', f'DA{j}')])
            c(f'DN{j}_S', [('in', f'DN{j}'), ('trim', f'DN{j}')])
        for k in range(8):
            c(f'XE{k}', [('gate', f'XE{k}')], (s(det['XE'] + k * XP),))
            c(f'XD{k}', [('gate', f'XD{k}')], (s(det['XD'] + k * XP),))
        for i, (n, key) in enumerate((('ENBM', 'pdM'), ('ENBQ', 'pdQ'))):
            # header-gate feed: a column from the inverter up to the top edge; the pull-down gates hang on it by a Metal4 jog
            yj = s(ys + st.rail_h + 1.0 + 0.8 * i)
            c(n + '_T', [('preQ', n)], (self.feed_y[n],))
            c(n, [(key, n)], (yj,))
            xa, xb = self.pin[n + '_T'][0], self.pin[n][0]
            self.g.rect('metal4', min(xa, xb) - 0.2, yj - 0.2, max(xa, xb) + 0.2, yj + 0.2)
            self.g.via(xa, yj, 3, 4)
            self.g.via(xb, yj, 3, 4)
        for n in ('TGM', 'TGMB', 'EXTM', 'ENMI'):
            c(n, [('preQ', n), ('preM', n)])
        link('RUNI', ('in', 'RUNI'), ('preM', 'RUNI'))
        link('RUNI_Q', ('in', 'RUNI'), ('preQ', 'RUNI'))
        link('RUNB', ('in', 'RUNB'), ('preM', 'RUNB'))
        for n in ('EXTB', 'EXTF', 'ENM0'):
            link(n, ('preM', n), ('preQ', n))
        link('POLB', ('in', 'POLB'), ('gate', 'POLB'))
        c('RUN', [('in', 'RUN')], (0.2,))
        link('RUN_M', ('in', 'RUN'), ('preM', 'RUN'))
        link('RUN_Q', ('preM', 'RUN'), ('preQ', 'RUN'))
        c('POL', [('gate', 'POL')], (0.2,))
        link('POL_M', ('gate', 'POL'), ('in', 'POL'))
        c('ENP', [('gate', 'ENP')], (0.2,))
        for n in ('ENM', 'OVP', 'OVN'):
            c(n, [('in', n)], (0.2,))
        for n in ('EXT', 'EN_MAIN'):
            pin(n, ('preM', n))
        pin('EN_POST', ('preQ', 'EN_POST'))
        self.finish()
        self.rail_m2()
        g = self.g
        self.bcore = 1.3                     # bus ends over the pull-downs: narrow stripes (no current)
        for n, yb in self.bus.items():
            g.rect('metal5', W - PD_W, ys + yb, W, ys + yb + self.bcore)
        self.bus_vias('pdM')
        self.bus_vias('pdQ')
        # the rail's own contact strip stops before the pull-down zone: an L-shaped contact area comes back from the GDS
        # with a sliver (CO.1 in Magic after `gds read`)
        g.r = [(l, x1, y1, min(x2, s(W - PD_W + 0.15)) if (l == 'psubdiffcont' and abs(y1 - (ys + 0.185)) < 0.01 and x1 < 1.0) else x2, y2)
               for l, x1, y1, x2, y2 in g.r]
        g.rect('psubdiff', W - PD_W + 0.45, ys + 0.05, W - 0.45, ys + st.rail_h - 0.05)       # one tap region under both strips
        g.rect('psubdiffcont', W - PD_W + 0.55, ys + 0.185, W - 0.55, ys + st.rail_h - 0.185)
        a, b = ys + st.up_to - 0.9, ys + st.up_to - 0.3
        g.rect('psubdiff', W - PD_W + 0.45, a + 0.05, W - 0.45, b - 0.05)
        g.rect('psubdiffcont', W - PD_W + 0.55, a + 0.185, W - 0.55, b - 0.185)
        for row_, nets in (('in', ('RUNB', 'DRB0', 'DRB1', 'DRB2', 'DRB3')), ('preM', ('EXTB', 'EXTF', 'RXB', 'ENM0')),
                           ('preQ', ('ENMI', 'ENQN', 'ENBM', 'ENBQ')), ('trim', tuple(ttr))):
            for n in nets:
                g.label(n, 'metal2', self.rows[row_][0].ext[n][0] + 0.2, self.ty(row_, n))
        self.leak(P)

    def leak(self, P):
        """nleak series NMOS (w / l = det.leak) per pump from DN j to VSS: four vertical diffusion lines under common poly
        plates (gate = VDD, contacted on the rows' VDD rails); DN end at the bottom on the trim strip's DN tracks."""
        g, D, tr = self.g, P['det'], self.rows['trim'][0]
        wl, ll = D['leak']
        xs_ = [s(-1.25 - 0.7 * j) for j in range(4)]
        y0 = s(max(self.ty('trim', f'DN{j}') for j in range(4)) + 0.6)
        pad, ph = 0.37, 0.5
        yg0 = s(y0 + ph + 0.4)
        yt = s(yg0 + D['nleak'] * (ll + 0.5) - 0.5 + 0.4)             # lower edge of the VSS pads
        if yt < self.ys + RAIL_W + 0.3:
            raise RuntimeError('leak column ends below the stack rail: the VSS strap of this generator does not fit')
        for j, x in enumerate(xs_):
            g.rect('ndiff', x - wl / 2, y0 + ph, x + wl / 2, yt)
            for ya in (y0, yt):
                g.rect('ndiff', x - pad / 2, ya, x + pad / 2, ya + ph)
                g.rect('ndiffc', x - CW / 2, ya + 0.07, x + CW / 2, ya + ph - 0.07)
            ty = self.ty('trim', f'DN{j}')
            g.rect('metal1', x - 0.17, ty - 0.19, x + 0.17, y0 + ph)
            g.rect('metal1', x - 0.19, ty - 0.19, x + 0.19, ty + 0.19)
            g.rect('via1', x - 0.13, ty - 0.13, x + 0.13, ty + 0.13)
            g.rect('metal2', x - 0.2, ty - 0.2, tr.ext[f'DN{j}'][0] + 0.2, ty + 0.2)
            self.net += [fet(f'dl{j}_{i}', 'n', f'DN{j}' if i == 0 else f'dlk{j}_{i - 1}', 'VDD',
                             'VSS' if i == D['nleak'] - 1 else f'dlk{j}_{i}', wl, ll) for i in range(D['nleak'])]
        rails = [self.rows[n][1] for n in ('in', 'preQ')]              # lower edges of the two VDD rails
        for i in range(D['nleak']):
            ya = s(yg0 + i * (ll + 0.5))
            g.rect('polysilicon', xs_[-1] - wl / 2 - 0.25, ya, xs_[0] + wl / 2 + 0.3, ya + ll)
            yr = [y for y in rails if ya + 0.5 < y and y + RAIL_W < ya + ll - 0.5]
            if not yr:
                raise RuntimeError('no VDD rail beside a leak gate plate')
            yr = yr[0]
            g.rect('polysilicon', xs_[0] + wl / 2, yr - 0.1, -0.3, yr + RAIL_W + 0.1)
            g.rect('polycontact', -0.715, yr + 0.185, -0.485, yr + 0.415)
            g.rect('metal1', -0.85, yr, 0.5, yr + RAIL_W)
        # VSS: Metal1 bar over the upper pads -> the stack-level VSS rail of the rows; substrate tap strip on the left
        g.rect('metal1', -LEAK_W + 0.15, yt, 1.0, yt + ph)
        g.rect('metal1', 0.4, self.ys + 0.1, 1.0, yt + ph)
        xt = -LEAK_W + 0.4
        g.rect('psubdiff', xt - 0.25, y0, xt + 0.25, yt + ph)
        g.rect('psubdiffcont', xt - 0.115, y0 + 0.135, xt + 0.115, yt + ph - 0.135)
        g.rect('metal1', xt - 0.2, y0, xt + 0.2, yt + ph)


# ------------------------------------------------------------------------------------------------ top
EM_I = 26.0                  # mA: bank current the metal is sized for (DC average; provisional bound, see em_table)
LIM14, LIM5 = 2.09, 4.5      # mA/um at 85 C: Metal1-4, Metal5 (GF180MCU DRM 14.2, as spec/power-delivery.md)
CUT = 0.58                   # mA per via cut at 85 C (as revision 2 / layout_engine)
BUS_WMAX = 5.5               # widest bus segment the 8 um slot pitch takes
RL_D = (10.0, 10.5, 11.0, 11.5, 12.0, 9.5, 12.5, 13.0)     # half distance of an RL pair
SW = (4.0, 4.5)                                           # half width of a bus -> RL strap (Metal3 || Metal4)
BUS_GROW = dict(MAIN_N=-1, MAIN_P=-1, POST_P=-1, POST_N=1)     # side on which a bus is widened beyond BCORE (gaps stay >= revision 2's)
HDR_RAIL = 4.0               # header VDD rail height (Metal1-4 continuous under the output risers)
RIGHT_W = 7.8                # column right of the last slice: the two AVG resistors and their substrate tap
RES = {'wtx_mx_rl': 'rl', 'wtx_mx_rcm': 'rcm', 'wtx_mx_ravg': 'ravg'}


def bus_width(n, i_bank=EM_I):
    """Metal5 width of a bus segment that carries n / 8 of the bank current (static data): <= 80 % of the Metal5 limit."""
    w = max(BCORE, math.ceil(n / 8 * i_bank / (0.8 * LIM5) / 0.05 - 1e-9) * 0.05)
    if w > BUS_WMAX:
        raise RuntimeError(f'no bus width for {n}/8 of {i_bank} mA')
    return s(w)


def place_clusters(sl, X0, hw, cx):
    """cluster centre, RLP side, strap half widths and RL half distance per bank such that every bus -> RL strap (Metal3 ||
    Metal4, under the buses above its own) clears the drain columns of those buses; taps as close to the array centre as
    possible (the bus current on the heavier side of a tap sets the bus width)."""
    W, st = sl.W, sl.st
    xc = X0 + 4 * W
    above = {n: BUS_ORDER[i + 1:] for i, n in enumerate(BUS_ORDER)}
    colx = {n: sorted(X0 + p * W + x for p in range(8) for x in st.col_x[n]) for n in BUS_ORDER}

    necks = [X0 + q * W for q in range(9)]
    axes = [max(a for a in (GRID_AX0 + 35.0 * k for k in range(-2, 12)) if a <= nq) for nq in necks]

    def riser_ok(x):               # output riser (Metal5 to the top edge) clear of the PH lanes and the grid VSS landings
        return all(not (nq + LANE[0] - 0.6 - RISER < x < nq + LANE[1] + 0.6 + RISER) for nq in necks[:8]) and \
            all(abs(x - a) >= LAND_HW + 0.6 + RISER for a in axes[:8])

    def half(n, x):
        if not riser_ok(x):
            return None
        for sw in SW:
            r = (x - X0) % W
            if any(rr + sw > STRAP_KEEP[0] and rr - sw < STRAP_KEEP[1] for rr in (r, r - W)):
                continue
            if all(abs(x - c) >= sw + STUB / 2 + 0.35 for m in above[n] for c in colx[m]):
                return sw
        return None
    cand = {}
    for tag, op, on in (('M', 'MAIN_P', 'MAIN_N'), ('Q', 'POST_P', 'POST_N')):
        v = []
        for D in RL_D:
            for k in range(int((8 * W - 2 * hw) / 0.05)):
                xb = s(X0 + hw + 1.0 + k * 0.05)
                for sd in (-1, 1):
                    a, b = half(op, xb + sd * D), half(on, xb - sd * D)
                    if a and b:
                        v.append((max(abs(xb - D - xc), abs(xb + D - xc)) - 0.01 * (a + b), xb, sd, a, b, D))
        cand[tag] = sorted(v, key=lambda c: c[1])
    best, q, suf = None, cand['Q'], []
    for c in reversed(q):                              # suffix minimum of the POST cluster's cost over its centre x
        suf.append(c if not suf or c[0] < suf[-1][0] else suf[-1])
    suf.reverse()
    j = 0
    for m in cand['M']:
        while j < len(q) and q[j][1] - m[1] < 2 * cx:
            j += 1
        if j == len(q):
            break
        cost = (max(m[0], suf[j][0]), m[0] + suf[j][0])
        if best is None or cost < best[0]:
            best = (cost, m[1:], suf[j][1:])
    if best is None:
        raise RuntimeError('no load cluster position clears the drain columns')
    return best[1], best[2]


def build_top(P=None, work=None, checks=True):
    P = dict(mux8.P, **(P or {}))
    work = Path(work or WORK / 'build')
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    sl = Slice(P)
    run_tcl(work, SLICE, sl.g.tcl(SLICE))
    ri = gen_res(work, {c: (('ppolyf_u_1k' if k == 'ravg' else 'ppolyf_u'),) + tuple(P[k]) for c, k in RES.items()})
    ctl = Ctl(P, sl)
    X0, W, H, ys, st = s(LEAK_W + ctl.W), sl.W, sl.H, sl.ys, sl.st
    xs = lambda p_: s(X0 + p_ * W)
    pos = {k: p_ for p_, k in enumerate(ORDER)}
    grid_axes = [max(a for a in (GRID_AX0 + 35.0 * k for k in range(-2, 12)) if a <= xs(q)) for q in range(8)]
    g = Geo()
    g.place(ctl.g, LEAK_W)
    inst, em, geo = [], {}, {}
    for p_, k in enumerate(ORDER):
        inst += [f'getcell {SLICE} child 0 0 parent {xs(p_)} 0', f'identify XS{k}']
    # ---- ring wires (Metal4), all of the same length
    for name, po, pi in (('BM', 'BMO', 'BMI'), ('BQ', 'BQO', 'BQI'), ('UP', 'UPI', 'UPO'), ('VP', 'VPI', 'VPO')):
        xa, xb = sl.pin[po][0], sl.pin[pi][0]
        for k, d, r, lo, hi, tr in ring_plan():
            y = s(sl.ring_y[name] + tr * RT_P[name])
            g.rect('metal4', xs(lo) + min(xa, xb) - 0.2, y - 0.2, xs(hi) + max(xa, xb) + 0.2, y + 0.2)
            g.via(xs(d) + xa, y, 3, 4)
            g.via(xs(r) + xb, y, 3, 4)
            g.label(f'{name}{(k - 1) % 8}', 'metal4', xs(lo) + min(xa, xb) + 0.5, y)
    # ---- detector wires (Metal4): XE k / XD k from slice k to the pump chains in the control block, all of the same length
    for n in ('XE', 'XD'):
        x_lo = s(LEAK_W + min(ctl.pin[f'{n}{k}'][0] for k in range(8)) - 0.2)
        x_hi = s(xs(7) + sl.pin[n][0] + 0.2)
        for k in range(8):
            y = s(sl.det_y[n] + k * XP)
            g.rect('metal4', x_lo, y - 0.2, x_hi, y + 0.2)
            g.via(LEAK_W + ctl.pin[f'{n}{k}'][0], y, 3, 4)
            g.via(xs(pos[k]) + sl.pin[n][0], y, 3, 4)
            g.label(f'{n}{k}', 'metal4', x_lo + 0.5, y)
        geo[f'{n}_track_um'] = round(x_hi - x_lo, 1)
    # ---- power: Metal5 VSS straps on the slice boundaries, VDD straps inside the slices, via stacks on the rails
    y_vdd = [sl.rows['in'][1], sl.rows['preQ'][1]]
    y_vss = [sl.rows['gate'][1], sl.rows['preM'][1]]
    for p_ in range(9):
        xb = xs(p_)
        g.rect('metal5', xb - VSS_W / 2, 0, xb + VSS_W / 2, ys + st.rail_h)
        for yr in y_vss:
            em['vss_logic_cuts'] = g.varr(xb - VSS_S, yr + 0.05, xb + VSS_S, yr + 0.55, 2, 5)
        em['vss_strap_cuts'] = g.varr(xb - VSS_W / 2 + 0.2, ys + 0.2, xb + VSS_W / 2 - 0.2, ys + st.rail_h - 0.2, 2, 5)
    xvdd = [xs(p_) + sl.vdd_x for p_ in range(8)]       # the control block (static logic) hangs on the rails of slice 0
    for xv in xvdd:
        g.rect('metal5', xv - VDD_W / 2, 0, xv + VDD_W / 2, y_vdd[1] + 0.9)
        for yr in y_vdd:
            em['vdd_logic_cuts'] = g.varr(xv - VDD_S, yr + 0.05, xv + VDD_S, yr + 0.55, 2, 5)
    # ---- loads, upside down: RL pair (output head down) / TOP plate / RCM / TOP2 plate / header (VDD rail at the top edge)
    nfh = nfing(P['hdr'], 3.2)
    while nfh % 2 or abs(round(P['hdr'] / nfh * 200) - P['hdr'] / nfh * 200) > 1e-6:
        nfh += 1
    wh = P['hdr'] / nfh
    hw = s(nfh * 0.44 + 0.6)
    cx = s(hw + 1.9)
    pm, pq = place_clusters(sl, X0, hw, cx)
    ports, taps, straps = {}, {}, []
    rl, rc, rv = ri['wtx_mx_rl'], ri['wtx_mx_rcm'], ri['wtx_mx_ravg']
    yA = s(H + 2.4)                                     # lower edge of the RL output pads
    yl = s(yA + 3.0 + rl['py'])                         # RL centre
    yw0 = s(yl + rl['py'] + 0.3)
    yr = s(yw0 + 3.3 + rc['py'])                        # RCM centre (TOP plate 1 um higher than revision 2: static data)
    yh = s(yr + rc['py'] + 1.3)                         # header: ends of its drain strips
    feeds = []
    for bi, (tag, (xb, sd, swp, swn, D), enb, op, on) in enumerate((('M', pm, 'ENBM', 'MAIN_P', 'MAIN_N'), ('Q', pq, 'ENBQ', 'POST_P', 'POST_N'))):
        top2, topn = f'TOP2{tag}', f'TOP{tag}'
        cols = [('c', 'VDD')]
        for f in range(nfh):
            cols += [('g', enb, wh), ('c', top2 if f % 2 == 0 else 'VDD')]
        hs = Strip('p', cols, {}, {'VDD': 'down', top2: 'up'}, rail_h=HDR_RAIL, gate_bar=True)
        hs.build()
        hx0 = s(xb - (hs.x[0] + hs.x[-1]) / 2)
        g.place(hs.geo, hx0, yh, hs.top)
        ytop = s(yh + hs.top)
        inst += [f'getcell wtx_mx_rcm child 0 0 parent {s(xb)} {yr}', f'identify XRCM{tag}']
        xu = hs.col_x[top2]
        for m in (1, 2):                                # TOP2 plate: RCM upper head -> header drains
            g.rect(f'metal{m}', xb - rc['hx'], yr + rc['c1'][0] - 0.1, xb + rc['hx'], yh - 1.0)
            g.rect(f'metal{m}', hx0 + xu[0] - 0.3, yh - 1.0, hx0 + xu[-1] + 0.3, yh + 0.2)
        g.rect('via1', hx0 + xu[0], yh - 0.9, hx0 + xu[-1], yh - 0.1)
        # TOP plate: RL upper heads -> RCM lower head on Metal1 .. Metal4 (static data: one RL feeds the whole RCM width)
        for m in (1, 2):
            g.rect(f'metal{m}', xb - rc['hx'], yw0, xb + rc['hx'], yr + rc['c0'][1] + 0.1)
        g.varr(xb - rc['hx'], yw0, xb + rc['hx'], yw0 + 3.0, 1, 4)
        geo['top_plate'] = dict(metal_um=round(2 * (yr + rc['c0'][1] + 0.1 - yw0) + 2 * 3.0, 2), rcm_half=rc['hx'], rl_half=rl['hx'])
        g.label(topn, 'metal1', xb, yw0 + 1.0)
        g.label(top2, 'metal1', xb, yh - 0.5)
        for o, xr, sw in ((op, s(xb + sd * D), swp), (on, s(xb - sd * D), swn)):
            inst += [f'getcell wtx_mx_rl child 0 0 parent {xr} {yl}', f'identify XRL{o[-1]}{tag}']
            for m in (1, 2):
                g.rect(f'metal{m}', xr - rl['hx'], yl + rl['c1'][0] - 0.1, xr + rl['hx'], yw0)
            # output pad under the lower head (Metal1 .. Metal4), strap Metal3 || Metal4 down to the bus, Via4 onto it
            g.rect('metal1', xr - rl['hx'], yA, xr + rl['hx'], yl + rl['c0'][1] + 0.1)
            em['rl_pad_cuts12'] = g.varr(xr - rl['hx'], yA, xr + rl['hx'], yl - rl['py'] - 0.3, 1, 2)
            em['rl_pad_cuts'] = g.varr(xr - sw, yA, xr + sw, yl - rl['py'] - 0.3, 2, 4)
            yb = ys + sl.bus[o]
            for m in (3, 4):
                g.rect(f'metal{m}', xr - sw, yb + 0.1, xr + sw, yA + 0.5)
            taps[o] = (xr, sw)
            straps.append((xr - sw - 0.7, xr + sw + 0.7))
            g.varr(xr - RISER, yA + 0.1, xr + RISER, yA + 1.5, 4, 5)       # pin: Metal5 riser from the pad to the top edge
            g.rect('metal5', xr - RISER, yA + 0.1, xr + RISER, ytop)
            ports[o] = ('metal5', xr, ytop - 0.5)
        # header VDD: Metal2 .. Metal5 on the rail (top edge), open where the two output risers pass
        # ... and where the PH lanes and the grid VSS landings come down from the top edge
        opn = sorted([(xb - D - RISER - 0.7, xb - D + RISER + 0.7), (xb + D - RISER - 0.7, xb + D + RISER + 0.7)] +
                     [(xs(q) + LANE[0] - 0.6, xs(q) + LANE[1] + 0.6) for q in range(8)] +
                     [(a - LAND_HW - 0.6, a + LAND_HW + 0.6) for a in grid_axes])
        segs, x_, hx1 = [], hx0, hx0 + hs.width
        for a, b in opn:
            a, b = max(a, hx0), min(b, hx1)
            if b <= a:
                continue
            if a - x_ >= 1.0:
                segs.append((x_, a))
            x_ = max(x_, b)
        if hx0 + hs.width - x_ >= 1.0:
            segs.append((x_, hx0 + hs.width))
        geo['hdr_vdd_um'] = round(min(geo.get('hdr_vdd_um', 1e9), sum(b - a - 0.4 for a, b in segs)), 1)
        for a, b in segs:
            g.varr(a + 0.2, ytop - hs.rail_h + 0.2, b - 0.2, ytop - 0.2, 2, 5)
            ports.setdefault('VDD', []).append(('metal5', s((a + b) / 2), ytop - 1.5))
        # ... and Metal2-4 right across, under the risers: every segment is fed through the rail itself (block top feeds one end)
        g.varr(hx0 + 0.2, ytop - hs.rail_h + 0.2, hx0 + hs.width - 0.2, ytop - 0.2, 2, 4)
        geo.setdefault('hdr_rail', {})[tag] = dict(metal_um=round(2 * hs.rail_h + 2 * (hs.rail_h - 0.4), 2), outer_seg_um=round(segs[0][1] - hx0, 2), width_um=round(hs.width, 2))
        for xt in [s(xb - hw - 1.3)] + ([s(xb + hw + 2.5)] if tag == 'Q' else []):      # substrate taps of the resistors
            g.rect('psubdiff', xt - 0.25, H + 0.5, xt + 0.25, ytop)
            g.rect('psubdiffcont', xt - 0.115, H + 0.635, xt + 0.115, ytop - 0.135)
            g.rect('metal1', xt - 0.2, H - 1.0, xt + 0.2, ytop)
        feeds.append((enb, s(hx0 + hs.pad[0]), s(yh + hs.top - hs.pad[1])))
        geo[f'hdr_{tag}'] = dict(fingers=nfh, w=wh)
    Htop = ytop
    # ---- tap landing: wtx8_aux's input pair sits between the two MAIN load resistors (wtx8_aux_layout.py draws it there);
    #      a 0.4 um Metal2 stub from each RL output pad to the pair's gate pad, same length on both sides
    xbm, sdm, Dm = pm[0], pm[1], pm[4]
    geo['tap'] = dict(xb=xbm, sd=sdm, yA=yA, y_wire_lo=s(yA + 3.5), y_wire_hi=s(yw0 - 0.6), landing={})
    for o, sg in (('MAIN_P', sdm), ('MAIN_N', -sdm)):
        xin, xl = s(xbm + sg * (Dm - rl['hx'] + 0.3)), s(xbm + sg * 1.0)
        g.rect('metal2', min(xin, xl - sg * 0.2), yA + 2.1, max(xin, xl - sg * 0.2), yA + 2.5)
        g.rect('metal2', xl - 0.2, yA + 2.1, xl + 0.2, yA + 3.4)
        geo['tap']['landing'][o] = [xl, s(yA + 3.2)]
        geo['tap'].setdefault('stub_um', {})[o] = round(abs(xin - xl) - 0.3 + 1.1, 2)
    # ---- drawn resistance of the speed-critical wires (for add_wire_r): lumped, driver -> gates
    RS, RS5 = 0.09, 0.04                 # ohm / square: Metal1-4, Metal5 (PDK Magic tech file `resist`)
    col = lambda n: (sl.pin[n][2] - sl.pin[n][1]) / 0.4 * RS
    gtr = (st.x[-1] - st.x[0]) / 0.4 * RS / 3          # Metal1 gate track of the stack, one entry, distributed
    trk = lambda row, n: (sl.rows[row][0].ext[n][1] - sl.rows[row][0].ext[n][0]) / TRACK_W * RS
    ring = lambda a, b: col(a) + (2 * W + abs(sl.pin[a][0] - sl.pin[b][0])) / 0.4 * RS + col(b) + gtr
    geo['wire_r'] = dict(
        sheet=dict(metal1_4=RS, metal5=RS5),
        trunks={'X': round(col('X') + trk('in', 'X') / 2, 2), 'XTM': round(trk('preM', 'XTM') / 2, 2), 'XTQ': round(trk('preQ', 'XTQ') / 2, 2),
                'APM': round(col('APM') + gtr, 2), 'ANM': round(col('ANM') + gtr, 2), 'APQ': round(col('APQ') + gtr, 2), 'ANQ': round(col('ANQ') + gtr, 2),
                'BM': round(ring('BMO', 'BMI'), 2), 'BQ': round(ring('BQO', 'BQI'), 2)},
        bus={n: dict(tap_x=taps[n][0], strap=round(RS / 2 * (yA + 0.5 - ys - sl.bus[n]) / (2 * taps[n][1]), 3)) for n in BUS_ORDER},
        x0=X0, pitch=W, order=ORDER)
    geo.update(nfb=st.nfb, wbf=P['wb'] / st.nfb, rail_h=st.rail_h, nfh=nfh, rl_hx=rl['hx'], rc_hx=rc['hx'])
    for enb, px, py in feeds:       # header gate: control block's feed column -> Metal2 along the slices' top edge -> poly pad
        xf, yj = s(LEAK_W + ctl.pin[enb + '_T'][0]), ctl.feed_y[enb]
        g.via(xf, yj, 2, 3)
        g.rect('metal2', min(xf, px) - 0.2, yj - 0.2, max(xf, px) + 0.2, yj + 0.2)
        g.rect('metal2', px - 0.2, yj - 0.2, px + 0.2, py + 0.2)
        g.via(px, py, 1, 2)
    # ---- output buses (Metal5): every slice draws the BCORE stripe; the top widens each segment for the current it carries
    bw_tab = {}
    for n in BUS_ORDER:
        yb, xt = ys + sl.bus[n], taps[n][0]
        bw_tab[n] = []
        allc = [xs(p_) + x for p_ in range(8) for x in st.col_x[n]]
        for p_ in range(8):
            # slices whose current passes this segment (static data): whole slices beyond it; in the tap's own slice the
            # drain columns on the heavier side of the tap, each column half a slice
            nl = sum(1 for c in allc if c < min(xt, xs(p_ + 1))) / 2
            nr_ = sum(1 for c in allc if c > max(xt, xs(p_))) / 2
            nn = nl if xs(p_ + 1) <= xt else nr_ if xs(p_) >= xt else max(nl, nr_)
            w_ = bus_width(nn)
            bw_tab[n].append((nn, w_))
            g.rect('metal5', xs(p_), yb - (w_ - BCORE if BUS_GROW[n] < 0 else 0), xs(p_ + 1), yb + (BCORE if BUS_GROW[n] < 0 else w_))
        xr, sw = taps[n]
        wt = bus_width(max(nn for nn, _ in bw_tab[n]))
        y1b, y2b = (yb - (wt - BCORE), yb + BCORE) if BUS_GROW[n] < 0 else (yb, yb + wt)
        g.rect('metal5', xr - sw, y1b, xr + sw, y2b)
        g.rect('metal4', xr - sw, y1b + 0.1, xr + sw, yb + 0.5)     # Metal4 only under the widened part (Metal3 columns end there)
        own = sorted(c for c in [xs(p_) + x for p_ in range(8) for x in st.col_x[n]] if xr - sw - 0.6 < c < xr + sw + 0.6)
        edges = [xr - sw] + [v for c in own for v in (c - 0.6, c + 0.6)] + [xr + sw]      # Via4 between the net's own column stacks
        em.setdefault('bus_tap_cuts', {})[n] = sum(g.varr(max(a_, xr - sw), y1b + 0.1, min(b_, xr + sw), y2b - 0.1, 4, 5)
                                                   for a_, b_ in zip(edges[::2], edges[1::2]) if min(b_, xr + sw) - max(a_, xr - sw) > 0.6)
    # ---- PH access path (shielded) and grid VSS tie verticals, the same in every slice
    yrail = (ys, ys + st.rail_h)                           # stack VSS rail (Metal2-5 on the VSS strap)
    nlo = ys + sl.bus['MAIN_N'] + BCORE - max(w for _, w in bw_tab['MAIN_N'])     # lowest bus edge
    nhi = ys + sl.bus['POST_N'] + max(w for _, w in bw_tab['POST_N'])            # highest bus edge
    wy0, wy1 = s(nhi + 0.75), s(nhi + 0.75 + 4.6)
    yA3 = s(yrail[0] - 4.0)                                # top of PH_A (Metal4 tracks end below it)
    yj1 = s(yrail[1] + 2.6)                                # top of the Metal4 jog (below the lowest bus edge)
    if yj1 + 0.3 > nlo:
        raise RuntimeError('PH jog runs into the bus band')
    straps_x = [(taps[n][0] - taps[n][1], taps[n][0] + taps[n][1]) for n in BUS_ORDER]
    band = lambda n: ((ys + sl.bus[n] + BCORE - max(w for _, w in bw_tab[n]), ys + sl.bus[n] + BCORE) if BUS_GROW[n] < 0
                      else (ys + sl.bus[n], ys + sl.bus[n] + max(w for _, w in bw_tab[n])))
    gaps4 = sorted((s(band(n)[0] - 0.3), s(band(n)[1] + 0.3) if n != 'POST_N' else s(wy0)) for n in ('MAIN_P', 'POST_N'))
    phw, ties = [], []
    for p_ in range(8):
        xb = xs(p_)
        px = xb + sl.pin['PH'][0]
        a0, a1 = px + PH_A[0], px + PH_A[1]
        g.rect('metal3', px - 0.2, 0.3, a1, 0.7)                                  # pin -> PH_A
        g.rect('metal3', a0, 0.3, a1, yA3)
        g.via(s((a0 + a1) / 2), yA3 - 0.2, 3, 4)
        g.rect('metal4', a0, yA3 - 0.42, xb + PH_J[1], yA3 + 0.02)
        g.rect('metal4', xb + PH_J[0], yA3 - 0.42, xb + PH_J[1], yj1)
        g.via(xb + (PH_J[0] + PH_J[1]) / 2, yj1 - 0.2, 3, 4)
        g.rect('metal3', xb + PH_C[0], yj1 - 0.42, xb + PH_J[1], yj1 + 0.02)
        g.rect('metal3', xb + PH_C[0], yj1 - 0.42, xb + PH_C[1], wy0 + 1.0)
        g.via(xb + (PH_C[0] + PH_C[1]) / 2, wy0 + 0.6, 3, 4)
        g.rect('metal4', xb + WIN[0], wy0, xb + WIN[1], wy1)
        phw.append([s(xb + WIN[0]), wy0, s(xb + WIN[1]), wy1])
        ys0, ys1 = s(yj1 + 0.35), s(wy0 - 0.35)               # shield: Metal4 over PH, Metal3 beside, stitched; tied to the rail
        g.rect('metal4', xb + SH4[0], ys0, xb + SH4[1], ys1)
        g.rect('metal4', xb + SH4[0], yrail[1] - 0.5, xb + SH4[0] + 0.55, ys0 + 0.5)
        # window guard (VSS Metal4): left / right / top of the pad, joined to the shield (the tap straps nearby saw the pad)
        g.rect('metal4', xb + SH4[0], ys1 - 0.2, xb + SH4[0] + 0.5, wy1 + 0.7)
        g.rect('metal4', xb + WIN[1] + 0.3, wy0 - 0.3, xb + WIN[1] + 0.7, wy1 + 0.7)     # joined through the top guard
        g.rect('metal4', xb + SH4[0], wy1 + 0.3, xb + WIN[1] + 0.7, wy1 + 0.7)
        for a_, b_ in SH3:
            g.rect('metal3', xb + a_, ys0, xb + b_, wy1 + 0.7)
            for i_ in range(int((ys1 - ys0 - 0.6) / 4.0) + 1):         # stitch to the Metal4 shield every 4 um
                g.via(xb + (a_ + b_) / 2, ys0 + 0.3 + 4.0 * i_, 3, 4)
        # grid VSS tie vertical in this slice's neck zone, unless a tap strap uses the zone
        z0, z1 = xb + (VZONE[0] if p_ else -3.0), xb + VZONE[1]
        if any(a_ - 0.3 < z1 and b_ + 0.3 > z0 for a_, b_ in straps_x):
            continue
        bn = band('POST_N')                                    # Metal3 half width in the POST_N band (Metal4 is out there)
        g.rect('metal3', z0, yrail[0], z1, bn[0] - 0.3)
        g.rect('metal3', z1 - TIE_N3, bn[0] - 0.3, z1, bn[1] + 0.3)
        g.rect('metal3', z0, bn[1] + 0.3, z1, wy1 - 0.4)          # Metal3 ends below the pad top (wtx8_aux Metal3 sits just above)
        # Metal4 of the vertical is left out under the higher-C leg of each output pair (MAIN_P, POST_N bands): Metal3 only
        # there, so the vertical adds the same C to both legs of a pair (session 16 follow-up: pair C differences)
        y4, cuts4 = yrail[0], []
        for a_, b_ in gaps4:
            g.rect('metal4', z0, y4, z1, a_)
            g.varr(z0, max(y4, a_ - 2.0), z1, a_, 3, 4, metal=False)
            if b_ + 2.0 < wy0 - 2.5:                         # above the last gap the pad's own Via3 array stitches
                g.varr(z0, b_, z1, b_ + 2.0, 3, 4, metal=False)
            y4 = b_
        g.rect('metal4', z0, y4, z1, wy1)
        g.varr(z0, yrail[0], z1, yrail[1], 3, 4, metal=False)
        g.varr(z0, max(wy0 - 2.0, y4 + 0.1), z1, wy1 - 0.5, 3, 4, metal=False)
        yp5 = s(wy1 - 2.0)                                   # Metal5 pad 2.6 um above the top bus edge (was 0.75: POST_N C)
        g.varr(z0, yp5, z1, wy1, 4, 5)
        ties.append(dict(slice=p_, neck_x=s(xb), pad=[s(z0), yp5, s(z1), wy1], axis=s(grid_axes[p_])))
    geo['ph_access'] = dict(windows=phw, lanes=[[s(xs(q) + LANE[0]), s(xs(q) + LANE[1])] for q in range(8)], window_y=[wy0, wy1],
                            lane_keep=[[s(xs(q) + LANE[0] - 0.6), s(xs(q) + LANE[1] + 0.6)] for q in range(8)],
                            note='mux coordinates; window = PH Metal4 pad (slice q = ORDER[q]); lane = the ring router\'s Metal5, top edge -> window, Via4')
    geo['vss_ties'] = dict(pads=ties, grid_axes=[s(a) for a in grid_axes], land_hw=LAND_HW,
                           note='Metal5 pads on the VSS verticals; the block joins each to the landing at its axis (Metal5, top edge)')
    # ---- AVG resistors right of the last slice (guard-ringed PCells, rings tied to VSS): upper head under a
    #      0.6 um finger of the MAIN bus (via stack only), lower head on Metal3 down to the pin
    xe = xs(8)
    for o, pin_, dx in (('MAIN_N', 'AVG_N', 2.6), ('MAIN_P', 'AVG_P', 6.1)):
        xr, yb = s(xe + dx), s(ys + sl.bus[o] + BCORE / 2)
        yc = s(yb - (rv['c1'][0] + rv['c1'][1]) / 2)
        inst += [f'getcell wtx_mx_ravg child 0 0 parent {xr} {yc}', f'identify XRAVG{o[-1]}']
        g.rect('metal5', xe, yb - 0.3, xr + 0.4, yb + 0.3)
        g.rect('metal1', xr - rv['hx'], yb - 0.3, xr + rv['hx'], yb + 0.3)
        g.via(xr, yb, 1, 5)
        ylo = s(yc + (rv['c0'][0] + rv['c0'][1]) / 2)
        g.rect('metal1', xr - rv['hx'], ylo - 0.3, xr + rv['hx'], ylo + 0.3)
        g.via(xr, ylo, 1, 3)
        g.rect('metal3', xr - 0.2, 0.0, xr + 0.2, ylo + 0.2)
        ports[pin_] = ('metal3', xr, 0.2)
        geo.setdefault('avg_finger_um', {})[o] = round(xr + 0.4 - xe, 2)
    xt, yv = s(xe + 2.6 - 1.38), sl.rows['preM'][1]            # left bar of the rings -> the preM VSS rail (Metal2)
    g.rect('metal2', xe - 0.5, yv, xt + 0.2, yv + RAIL_W)
    g.rect('metal1', xt - 0.19, yv + 0.1, xt + 0.19, yv + RAIL_W - 0.1)
    g.rect('via1', xt - 0.13, yv + 0.17, xt + 0.13, yv + RAIL_W - 0.17)
    g.rect('metal1', xe + 2.6 + 1.265, yv, xe + 6.1 - 1.265, yv + RAIL_W)      # ring to ring (Metal1; the rings do not overlap)
    # ---- trim bits: Metal4 tracks from each slice's TR b column to the right edge (pins on the right side)
    xedge = s(xe + RIGHT_W)
    for p_, k in enumerate(ORDER):
        for b in range(NTR):
            xc, y = s(xs(p_) + sl.pin[f'TR{b}'][0]), sl.tr_ys[8 * b + p_]
            g.rect('metal4', xc - 0.2, y - 0.2, xedge, y + 0.2)
            g.via(xc, y, 3, 4)
            ports[f'TR{k}_{b}'] = ('metal4', s(xedge - 0.2), y)
            geo.setdefault('trim_track_um', {})[f'TR{k}_{b}'] = round(xedge - xc, 1)
    # ---- ports (order of wtx_mux8.PORTS)
    for p_, k in enumerate(ORDER):
        for n, name in (('PH', f'PH{k}'), ('F', f'F{k}')):
            ports[name] = ('metal3', xs(p_) + sl.pin[n][0], 0.2)
    for n in ('ENM', 'ENP', 'POL', 'EN_MAIN', 'EN_POST', 'EXT', 'OVP', 'OVN', 'RUN'):
        ports[n] = ('metal3', LEAK_W + ctl.pin[n][0], 0.2)
    ports['VDD'].append(('metal5', xs(0) + sl.vdd_x, 1.0))
    ports['VSS'] = ('metal5', xs(1), 1.0)
    for i, n in enumerate(mux8.PORTS):
        for layer, x, y in (ports[n] if isinstance(ports[n], list) else [ports[n]]):
            g.rect(layer, x - 0.2, y - 0.2, x + 0.2, y + 0.2)
            g.label(n, layer, x, y, i + 1)
    run_tcl(work, TOP, g.tcl(TOP, extra=inst))
    size = [s(xe + RIGHT_W), s(Htop)]
    res = dict(size_um=size, area_um2=round(size[0] * size[1], 1), slice_um=[W, H], control_um=[s(LEAK_W + ctl.W), H],
               loads_um=[s(pq[0] - pm[0] + 2 * hw + 0.6), s(Htop - H)], clusters=dict(M=pm, Q=pq), bus_width_um=bw_tab, geo=geo,
               free_top_corners_um=[[s(pm[0] - hw - 2.0), s(Htop - H - 2.0)], [s(size[0] - pq[0] - hw - 3.5), s(Htop - H - 2.0)]],
               pins={n: (v if isinstance(v, list) else [v]) for n, v in ports.items()}, taps=taps, em_cuts=em,
               P={k: v for k, v in P.items()})
    (work / 'geom.json').write_text(json.dumps(res, indent=1))
    return res, sl, ctl


# ------------------------------------------------------------------------------------------------ reports
def cap_table(path, sep='/'):
    """wiring capacitance (fF, ground + coupling, no device capacitance) from a flat Magic netlist: totals of the output
    nets with their largest partners, load nodes, and min / max over the eight slices of the phase-path nets."""
    tot, pair = {}, {}
    for l in Path(path).read_text().splitlines():
        if l.startswith('C'):
            tk = l.split()
            u = {'f': 1.0, 'p': 1e3, 'a': 1e-3, 'n': 1e6}.get(tk[3][-1])
            v = float(tk[3][:-1]) * u if u else float(tk[3]) * 1e15
            for a, b in ((tk[1], tk[2]), (tk[2], tk[1])):
                tot[a] = tot.get(a, 0.0) + v
                if a in BUS_ORDER:
                    key = b if b in BUS_ORDER + ('VSS', 'VDD') else 'slice S nodes' if b.endswith((sep + 'SM', sep + 'SQ')) else 'other'
                    pair.setdefault(a, {})[key] = pair.setdefault(a, {}).get(key, 0.0) + v
    out = {n: dict(total=round(tot.get(n, 0.0), 1), to={k: round(v, 1) for k, v in sorted(pair.get(n, {}).items(), key=lambda kv: -kv[1])})
           for n in BUS_ORDER}
    for n in ('TOPM', 'TOPQ', 'TOP2M', 'TOP2Q', 'AVG_P', 'AVG_N', 'RUN'):
        out[n] = round(tot.get(n, 0.0), 1)
    per = {}
    for n in ('SM', 'SQ', 'Y', 'Z', 'X', 'XTM', 'XTQ', 'APM', 'ANM', 'APQ', 'ANQ', 'EM', 'EQ', 'FB'):
        per[n] = [round(tot.get(f'XS{k}{sep}{n}', 0.0), 2) for k in range(8)]
    for n in ('BM', 'BQ', 'UP', 'VP', 'XE', 'XD', 'PH', 'F'):
        per[n] = [round(tot.get(f'{n}{k}', 0.0), 2) for k in range(8)]
    out['per_slice'] = per
    out['per_slice_min_max'] = {n: [min(v), max(v)] for n, v in per.items()}
    for n in ('ENM', 'ENP', 'OVP', 'OVN', 'RUNI', 'TGM', 'TGMB', 'EXTM', 'ENMI', 'ENQI', 'ENQIB', 'ENBM', 'ENBQ', 'POLB'):
        out[n] = round(tot.get(n, 0.0), 1)
    for j in range(4):
        out[f'DA{j}'], out[f'DN{j}'] = round(tot.get(f'DA{j}', 0.0), 1), round(tot.get(f'DN{j}', 0.0), 1)
    return out


def em_table(res, i_bank=EM_I):
    """electromigration table from the drawn geometry (res = build_top()'s record) for a bank current i_bank (mA, DC
    average at 85 C).  Normal operation: every slice carries the bank current for 1/8 of the time; EXT mode: all eight in
    parallel at DC: the same i_bank / 8 average per slice.  Data may be static (all current in one output leg / one RL).
    Each row: mA, metal width (um, layers in parallel added) or cuts, mA/um (or mA/cut), limit, margin %."""
    g, c, I = res['geo'], res['em_cuts'], float(i_bank)
    nfb = g['nfb']
    rows = {}

    def row(name, i, w, lim=LIM14):
        rows[name] = dict(mA=round(i, 3), um=round(w, 2), mA_per_um=round(i / w, 2), limit=lim, margin_pct=round(100 * (1 - i / w / lim), 1))

    def cut(name, i, n):
        rows[name] = dict(mA=round(i, 3), cuts=n, mA_per_cut=round(i / n, 3), limit=CUT, margin_pct=round(100 * (1 - i / n / CUT), 1))
    icol = I / 8 / (nfb // 4)                   # one drain column = two A fingers of one leg, static data
    row('drain column, half where it leaves (Metal1 0.23 + Metal2 UPW)', icol, CW + UPW)
    row('drain column, far half (Metal1 0.23 + Metal2 UPN)', icol / 2, CW + UPN)
    cut('drain column -> bus via stack (per level)', icol, 4)
    row('drain stub to an upper bus (Metal4)', icol, STUB)
    row('S column (Metal1 0.23; static data: half of the slice current crosses the S bar)', I / 8 / nfb, CW)
    row('S bar (Metal1)', I / 16, BAR_H)
    ivss = I / 8 / nfb * 2
    row('stack VSS column above its Metal2 (Metal1 0.4)', ivss * (1 - VSS_M2 / g['wbf']), 0.4)
    row('stack VSS column at the foot (Metal1 0.4 + Metal2 0.8)', ivss, 1.2)
    row('stack VSS rail per slice, two banks, to the two boundary straps (Metal1 + Metal2)', 0.57 * I / 4, 2 * g['rail_h'])
    cut('VSS strap via stack on the stack rail (two banks of two slices + 3 mA logic)', I / 4 + 3.0, c['vss_strap_cuts'])
    row('VSS Metal5 strap (two banks + 3 mA logic estimate)', I / 4 + 3.0, VSS_W, LIM5)
    for n in BUS_ORDER:
        nn, w = max(res['bus_width_um'][n], key=lambda v: v[0] / v[1])
        row(f'{n} bus, worst segment ({nn:g}/8 of the bank, Metal5)', nn / 8 * I, w, LIM5)
        row(f'{n} bus -> RL strap (Metal3 + Metal4)', I, 4 * res['taps'][n][1])
        cut(f'{n} strap -> bus Via4', I, c['bus_tap_cuts'][n])
    cut('RL output pad Via2 / Via3 (per level)', I, c['rl_pad_cuts'])
    cut('RL output pad Via1', I, c['rl_pad_cuts12'])
    row('RL heads (Metal1 + Metal2 tongue, one RL carries the bank: static data)', I, 4 * g['rl_hx'])
    tp = g['top_plate']
    for tag in ('M', 'Q'):
        D = res['clusters'][tag][4]
        row(f'TOP plate {tag}, lateral (static data: one RL feeds the whole RCM width; Metal1-4)',
            I * (tp['rcm_half'] + D - tp['rl_half']) / (2 * tp['rcm_half']), tp['metal_um'])
    row('RCM heads / TOP2 plate (Metal1 + Metal2)', I, 4 * g['rc_hx'])
    row('header column (Metal1 + Metal2)', 2 * I / g['nfh'], 1.2)
    row('header VDD rail at the top edge (Metal2-5; pins on Metal5)', I, g['hdr_vdd_um'], LIM5)
    for tag in ('M', 'Q'):
        hr = g['hdr_rail'][tag]
        row(f'header {tag} rail under the first riser, fed from one outer segment only (Metal1-4)', I * (1 - hr['outer_seg_um'] / hr['width_um']), hr['metal_um'])
    row('logic VDD Metal5 strap per slice (~3 mA estimate, not from simulation)', 3.0, VDD_W, LIM5)
    row('logic rails (Metal1 + Metal2, ~1.5 mA per rail and slice estimate, two directions)', 0.75, 2 * RAIL_W)
    worst = min(rows.items(), key=lambda kv: kv[1]['margin_pct'])
    return dict(i_bank_mA=I, rows=rows, worst=[worst[0], worst[1]['margin_pct']],
                max_i_bank_mA_at_zero_margin=round(I / (1 - worst[1]['margin_pct'] / 100), 1),
                note='limits: Metal1-4 2.09 mA/um, Metal5 4.5 mA/um, 0.58 mA per via cut (85 C).  The buses are sized for '
                     f'EM_I = {EM_I} mA at 80 % of the Metal5 limit; for another i_bank only the table changes, not the layout.')


# ------------------------------------------------------------------------------------------------ checks on the GDS from disk
def ref_netlist(P=None):
    return '* reference: wtx_mux8.netlist() (flat)\n' + mux8.netlist(P)


def negatives(sch):
    """LVS references that must NOT match the layout."""
    def sub(a, b):
        assert a in sch, a
        return sch.replace(a, b, 1)
    l0 = next(l for l in sch.splitlines() if l.startswith('XI1_0n_0 '))
    w0 = re.search(r' w=([\d.]+)u', l0).group(1)
    return {'neg_finger_wrong_output': sub('XMPM_3_0 MAIN_N APM3 SM3', 'XMPM_3_0 MAIN_P APM3 SM3'),
            'neg_slice_inputs_swapped': sub('XGU_2na1_0 U2 F2 ', 'XGU_2na1_0 U2 F3 ').replace('XGU_3na1_0 U3 F3 ', 'XGU_3na1_0 U3 F2 ', 1),
            'neg_device_width': sub(l0, l0.replace(f' w={w0}u', f' w={float(w0) * 1.1:.3f}u')),
            'neg_trim_bits_swapped': sub('XTS0_5_0 Y5 TR5_0 ', 'XTS0_5_0 Y5 TR5_1 ').replace('XTS1_5_0 Y5 TR5_1 ', 'XTS1_5_0 Y5 TR5_0 ', 1),
            'neg_detector_keeper3_from_xe3': sub('XDK3n_0 XH3 XS3 ', 'XDK3n_0 XH3 XE3 ').replace('XDK3p_0 XH3 XS3 ', 'XDK3p_0 XH3 XE3 ', 1)}


def export_gds(work, cell=TOP):
    """the GDS to publish: written by the analog image's Magic with `cif ostyle gdsii` (spec/block-deliverables.md, GDS export
    rule: the digital image's Magic omits the high-resistance marker 62/0 of ppolyf_u_1k)."""
    out = tools.gds_export_analog(work, cell)
    if not out.exists():
        raise RuntimeError('GDS export failed; see gdsx.log')
    final = Path(work) / f'{cell}.gds'
    shutil.move(out, final)
    return final


def verify(gds, work, cell=TOP, sch=None, negs=None, kl=True):
    """fresh directory, GDS read back: Magic DRC, extraction (separate session), LVS with properties, negative controls,
    Magic antenna check, KLayout DRC on the same file.  Leaves <cell>.lvs.spice and <cell>.ext.spice (flat, C only)."""
    work, gds = Path(work), Path(gds)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    shutil.copy(gds, work / f'{cell}.gds')
    rd = ['crashbackups stop', f'gds read {cell}.gds', f'load {cell}', 'select top cell', 'expand']
    drc = rd + ['drc euclidean on', 'drc style drc(full)', 'drc check', 'drc catchup', 'set f [open drc-count.txt w]',
                'puts $f [drc list count total]', 'close $f', 'set f [open drc-details.txt w]', 'puts $f [drc listall why]', 'close $f',
                'quit -noprompt']
    ext = rd + ['extract all', 'ext2spice lvs', f'ext2spice -o {cell}.lvs.spice', 'ext2spice default', 'ext2spice hierarchy off',
                'ext2spice subcircuit top on', 'ext2spice cthresh 0', f'ext2spice -o {cell}.ext.spice',
                'puts "ANTENNA-BEGIN"', 'antennacheck debug', 'antennacheck', 'puts "ANTENNA-END"', 'quit -noprompt']
    (work / 'drc.tcl').write_text('\n'.join(drc) + '\n')
    (work / 'ext.tcl').write_text('\n'.join(ext) + '\n')
    magic(work, 'drc.tcl')
    magic(work, 'ext.tcl')
    raw = (work / 'drc-count.txt').read_text().strip() if (work / 'drc-count.txt').exists() else 'missing'
    res = dict(gds=str(gds), sha256=tools.sha(gds), magic_drc=le.drc_errors(raw))
    sch = sch or ref_netlist()
    (work / 'sch.spice').write_text(sch)
    res['lvs'] = netgen(work, f'{cell}.lvs.spice', cell, 'sch.spice', cell, out='lvs.txt')
    lv = (work / 'lvs.txt').read_text() if (work / 'lvs.txt').exists() else ''
    res['lvs']['counts'] = [' '.join(l.split()) for l in lv.splitlines() if l.startswith(('Number of devices', 'Number of nets'))][-2:]
    res['lvs']['property_errors'] = lv.count('property errors') + lv.count('Property errors')
    res['negative_controls'] = {}
    for n, text in (negs if negs is not None else negatives(sch)).items():
        assert text != sch, n
        (work / f'{n}.spice').write_text(text)
        r = netgen(work, f'{cell}.lvs.spice', cell, f'{n}.spice', cell, out=f'lvs-{n}.txt')
        res['negative_controls'][n] = dict(fails_as_required=not r['unique_match'], summary=r['summary'][:160])
        (work / f'{n}.spice').unlink()
    log = (work / 'ext.tcl.log').read_text()
    ant = log[log.find('ANTENNA-BEGIN'):log.find('ANTENNA-END')] if 'ANTENNA-BEGIN' in log else 'not run'
    viol = [l for l in ant.splitlines() if 'violation' in l.lower()]
    res['antenna_magic'] = dict(violations=len(viol), lines=viol[:10], ran='ANTENNA-END' in log)
    (work / 'antenna.txt').write_text(ant + '\n')
    if kl:
        res['klayout_drc'] = tools.klayout_drc(work, work / f'{cell}.gds', cell)
        ant_rules = sorted(k for k in res['klayout_drc'].get('by_rule', {}) if 'ANT' in k)
        res['klayout_drc']['antenna_rules_flagged'] = ant_rules
        shutil.rmtree(work / 'klayout' / 'out', ignore_errors=True) if res['klayout_drc'].get('violations') == 0 else None
    for f in list(work.glob('*.ext')) + [work / f'{cell}.gds']:
        f.unlink()
    (work / 'verify.json').write_text(json.dumps(res, indent=1))
    return res


# ------------------------------------------------------------------------------------------------ extracted netlists
def fix_vsubs(text, cell=TOP):
    """documented post-process of a flat Magic netlist (review M6): the guard-ring-less ppolyf_u PCells are subcells without a
    substrate tap of their own, so the flat netlist puts their body (and their capacitance to substrate) on a floating
    `<instance>/VSUBS` (hierarchical extraction) or `VSUBS` (flattened) net.  The substrate under them is tied to VSS by the
    tap strips beside each load cluster (the LVS netlist shows VSS), so these nets are renamed to VSS; capacitors that then
    have both ends on VSS are dropped.  Returns (text, lines changed)."""
    out, n = [], 0
    for l in text.splitlines():
        tk = l.split()
        if tk and not l.startswith(('.', '*', '+')) and any(x == 'VSUBS' or x.endswith('/VSUBS') for x in tk[1:5]):
            tk = [tk[0]] + ['VSS' if (x == 'VSUBS' or x.endswith('/VSUBS')) else x for x in tk[1:5]] + tk[5:]
            n += 1
            if tk[0][0] == 'C' and tk[1] == tk[2]:
                continue
            l = ' '.join(tk)
        out.append(l)
    return '\n'.join(out) + '\n', n


def ports_of(text, cell=TOP):
    m = re.search(rf'\.subckt {cell} ((?:.*\n)(?:\+.*\n)*)', text)
    return m.group(1).replace('\n+', ' ').split()


def extract_rc(gds, work, cell=TOP, tol=10, ports=None):
    """flat R + C netlist (Magic extresist in the analog image; recipe of scratch/lo-ap4/rcx.py as used for wtx_ser8d: the
    digital image's Magic 8.3.623 is recorded as crashing in extresist).  Supplies and substrate are not resisted."""
    work, gds = Path(work), Path(gds)
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    shutil.copy(gds, work / 'in.gds')
    (work / 'rc.tcl').write_text('\n'.join(
        ['crashbackups stop', 'drc off', 'gds read in.gds', f'load {cell}', f'flatten {cell}_flat', f'load {cell}_flat', 'select top cell',
         'extract do capacitance', 'extract do coupling', 'extract do resistance', 'extract all', 'ext2sim labels on', 'ext2sim',
         f'extresist tolerance {tol}', 'extresist ignore VSS', 'extresist ignore VDD', 'extresist ignore VSUBS', 'extresist all',
         'ext2spice lvs', 'ext2spice hierarchy off', 'ext2spice format ngspice', 'ext2spice cthresh 0', 'ext2spice rthresh 0',
         'ext2spice extresist on', 'ext2spice subcircuit top on', f'ext2spice -o {cell}_flat.rc.spice', 'quit -noprompt']) + '\n')
    tools.run_analog(work, f'magic -dnull -noconsole -rcfile {tools.ANALOG_PDK}/libs.tech/magic/gf180mcuD.magicrc /work/rc.tcl > rc.log 2>&1')
    f = work / f'{cell}_flat.rc.spice'
    if not f.exists():
        return dict(ok=False, log=str(work / 'rc.log'))
    t, nfix = fix_vsubs(f.read_text().replace(f'{cell}_flat', cell), cell)
    # the flattened view names every separate piece of a supply net (<net>_uq<i>): the header rails of the two banks are
    # VDD islands of their own, joined to the logic VDD by the parent.  They are merged by name here, as the hierarchical
    # netlists do; their internal resistor nodes (<net>_uq<i>.n<k>) stay.
    uq = sorted(set(re.findall(r'\b(\w+)_uq\d+\b(?![.\w])', t)))
    t = re.sub(r'\b(\w+)_uq\d+\b(?![.\w])', r'\1', t)
    want = list(ports) if ports else (list(mux8.PORTS) if cell == TOP else None)
    if want:
        have = list(dict.fromkeys(ports_of(t, cell)))
        if set(have) != set(want):
            return dict(ok=False, why=f'ports differ: {sorted(set(have) ^ set(want))}')
        m_ = re.search(rf'\.subckt {cell} ((?:.*\n)(?:\+.*\n)*)', t)
        t = t[:m_.start()] + f'.subckt {cell} ' + ' '.join(want) + '\n' + t[m_.end():]
    (work / f'{cell}.rc.spice').write_text(t)
    for x in list(work.glob('*.ext')) + list(work.glob('*.sim')) + list(work.glob('*.nodes')) + list(work.glob('*.mag')) + [work / 'in.gds', f]:
        if x.exists():
            x.unlink()
    L = t.splitlines()
    cnt = lambda k: sum(1 for l in L if l.startswith('X') and k in l)
    return dict(ok=True, path=str(work / f'{cell}.rc.spice'), R=sum(l.startswith('R') for l in L), C=sum(l.startswith('C') for l in L),
                nfet=cnt('nfet_03v3'), pfet=cnt('pfet_03v3'), ppolyf_u=sum(1 for l in L if l.startswith('X') and ' ppolyf_u ' in l),
                ppolyf_u_1k=cnt('ppolyf_u_1k'), vsubs_lines_fixed=nfix, supply_pieces_merged=uq, tolerance=tol,
                ports_ok=(ports_of(t, cell) == want) if want else None,
                nets_with_R=len({re.sub(r'\.[nt]\d+$', '', l.split()[1]) for l in L if l.startswith('R')}))


def add_wire_r(text, res, pre='', sep='.', bus=None):
    """documented post-process of the flat R + C netlist: Magic extresist (repo recipe) returns the speed-critical nets
    without resistors, so the DRAWN resistance is added here from the generator's geometry (res['geo']['wire_r']):
      * gate-line trunks X, XT, AP, AN (both banks) of every slice and the ring wires B: one lumped resistor from the driver
        node (name unchanged) to a new node <net>#g that takes the receivers (gates; for X everything but I1's drains);
        Metal3 column + half the Metal2 track, or column + Metal4 ring wire + column, + 1/3 of the stack's Metal1 gate track;
        the net's wiring capacitors are split half / half between the two nodes;
      * output buses MAIN_P / MAIN_N / POST_P / POST_N: one node <bus>#<k> per slice k (stack drains), Metal5 ladder with the
        drawn width of each segment, the tap node <bus>#t where the strap lands, the strap (Metal3 || Metal4) from there to the
        net itself (RL, pin riser).  Pull-downs sit on the first slice's node, the AVG resistor on the last one's.  Capacitors
        to a slice's nets go to that slice's node; all others are split into eight equal parts along the bus.
    pre / sep / bus: instance prefix and hierarchy separator of the mux's nets and {mux bus name: net name} when the netlist
    is a block netlist (pt_wiredtx8: 'XMUX/', '/', POST_P / POST_N crossed).  Returns (text, table of the lumped values in ohm)."""
    wr = res['geo']['wire_r']
    order, x0, W = wr['order'], wr['x0'], wr['pitch']
    pos = {k: p for p, k in enumerate(order)}
    val = lambda x: (float(x[:-1]) * {'f': 1e-15, 'p': 1e-12, 'a': 1e-18, 'n': 1e-9}[x[-1]]) if x[-1] in 'fpan' else float(x)
    bus = bus or {n: n for n in BUS_ORDER}
    BUSN = set(bus.values())
    rsl = re.compile(re.escape(pre) + r'XS(\d)' + re.escape(sep))
    trunk = {}
    for k in range(8):
        for n in ('X', 'XTM', 'XTQ', 'APM', 'ANM', 'APQ', 'ANQ'):
            trunk[f'{pre}XS{k}{sep}{n}'] = wr['trunks'][n]
        trunk[f'{pre}BM{k}'], trunk[f'{pre}BQ{k}'] = wr['trunks']['BM'], wr['trunks']['BQ']
    out, extra, nres = [], [], 0
    busn = lambda n, k: f'{n}#{k}'
    for l in text.splitlines():
        tk = l.split()
        if not tk or l[0] in '.*+':
            out.append(l)
            continue
        if tk[0][0] == 'X' and len(tk) > 5 and 'fet_03v3' in tk[5]:
            d, g_, s_ = tk[1:4]
            for n in (d, g_, s_):
                if n in trunk and n.endswith(sep + 'X'):
                    if g_ != n[:-1] + 'Z':                     # not I1: a receiver of X
                        tk[1:4] = [x + '#g' if x == n else x for x in tk[1:4]]
            if g_ in trunk and not g_.endswith(sep + 'X'):
                tk[2] = g_ + '#g'
            m_ = re.match(re.escape(pre) + r'XS(\d)' + re.escape(sep) + r'A[PN][MQ]$', g_)
            if m_:
                tk[1], tk[3] = [busn(x, m_.group(1)) if x in BUSN else x for x in (tk[1], tk[3])]
            elif g_ in (pre + 'ENBM', pre + 'ENBQ') or g_.split('.')[0] in ('ENBM', 'ENBQ'):
                tk[1], tk[3] = [busn(x, order[0]) if x in BUSN else x for x in (tk[1], tk[3])]
            out.append(' '.join(tk))
        elif tk[0][0] == 'X' and 'ppolyf_u_1k' in l:
            out.append(' '.join([tk[0]] + [busn(x, order[-1]) if x in BUSN else x for x in tk[1:3]] + tk[3:]))
        elif tk[0][0] == 'C':
            a, b, v = tk[1], tk[2], val(tk[3])
            if a in BUSN or b in BUSN:
                if b in BUSN and a not in BUSN:
                    a, b = b, a
                m_ = rsl.match(b)
                if m_:
                    out.append(f'{tk[0]} {busn(a, m_.group(1))} {b} {v:.4g}')
                else:
                    out += [f'{tk[0]}_{k} {busn(a, k)} {busn(b, k) if b in BUSN else b} {v / 8:.4g}' for k in range(8)]
            elif a in trunk or b in trunk:
                out += [f'{tk[0]}_d {a} {b} {v / 2:.4g}', f'{tk[0]}_g {a + "#g" if a in trunk else a} {b + "#g" if b in trunk else b} {v / 2:.4g}']
            else:
                out.append(l)
        else:
            out.append(l)
    for n, r in trunk.items():
        extra.append(f'RWT{nres} {n} {n}#g {r}')
        nres += 1
    table = dict(trunks_ohm=wr['trunks'], bus={})
    for mn in BUS_ORDER:
        n = bus[mn]
        ws = [w for _, w in res['bus_width_um'][mn]]
        xt, cen = wr['bus'][mn]['tap_x'], [x0 + (p + 0.5) * W for p in range(8)]
        seg = []
        for p in range(7):
            r = wr['sheet']['metal5'] * (W / 2 / ws[p] + W / 2 / ws[p + 1])
            a, b = busn(n, order[p]), busn(n, order[p + 1])
            if cen[p] <= xt < cen[p + 1]:
                f = (xt - cen[p]) / W
                extra += [f'RWB{nres} {a} {n}#t {r * f:.4g}', f'RWB{nres + 1} {n}#t {b} {r * (1 - f):.4g}']
                nres += 2
            else:
                extra.append(f'RWB{nres} {a} {b} {r:.4g}')
                nres += 1
            seg.append(round(r, 3))
        extra.append(f'RWS{nres} {n}#t {n} {wr["bus"][mn]["strap"]}')
        nres += 1
        left = sum(r for p, r in enumerate(seg) if cen[p + 1] <= xt)
        table['bus'][n] = dict(segments_ohm=seg, strap_ohm=wr['bus'][mn]['strap'], end_to_tap_ohm=[round(left, 2), round(sum(seg) - left, 2)], tap_x_um=xt)
    i = max(k for k, l in enumerate(out) if l.startswith('.ends'))
    out = out[:i] + ['* drawn wire resistance added by wtx_mux8_layout.add_wire_r'] + extra + out[i:]
    table['resistors_added'] = len(extra)
    return '\n'.join(out) + '\n', table


# ------------------------------------------------------------------------------------------------ complete run
FAST = tools.GENERATED / 'fast'


def run_all(publish=True):
    """build -> checks in the build directory -> GDS (analog image) -> every check again on the GDS read back from disk in a
    fresh directory -> flat C netlist (VSUBS post-process) and R + C netlist -> report.json; copies to OUT and generated/fast."""
    res, sl, ctl = build_top()
    b = WORK / 'build'
    res['build_check'] = check(b, TOP, ref_netlist())
    gds = export_gds(b)
    v = verify(gds, WORK / 'verify')
    res['verify_from_disk'] = v
    raw = (WORK / 'verify' / f'{TOP}.ext.spice').read_text()
    before = [l for l in raw.splitlines() if 'VSUBS' in l and l.startswith('X')]
    fixed, nfix = fix_vsubs(raw)
    after = [l for l in fixed.splitlines() if ' ppolyf_u' in l]
    res['c_netlist'] = dict(vsubs_lines_fixed=nfix, resistor_lines_before=before, resistor_lines_after=after,
                            ports_ok=ports_of(fixed) == list(mux8.PORTS),
                            devices={k: sum(1 for l in fixed.splitlines() if l.startswith('X') and k in l) for k in ('nfet_03v3', 'pfet_03v3', 'ppolyf_u')},
                            floating_vsubs_left=sum(1 for l in fixed.splitlines() if 'VSUBS' in l))
    (WORK / 'verify' / f'{TOP}.ext.spice').unlink()               # written by the container's root
    (WORK / 'verify' / f'{TOP}.ext.spice').write_text(fixed)
    res['rc_netlist'] = extract_rc(gds, WORK / 'rc')
    if res['rc_netlist'].get('ok'):
        f = WORK / 'rc' / f'{TOP}.rc.spice'
        t_, res['rc_netlist']['wire_r_added'] = add_wire_r(f.read_text(), res)
        f.write_text(t_)
    res['wire_c_fF'] = cap_table(WORK / 'verify' / f'{TOP}.ext.spice')
    res['em_table'] = em_table(res)
    OUT.mkdir(parents=True, exist_ok=True)
    files = {gds: f'{TOP}.gds', WORK / 'verify' / f'{TOP}.ext.spice': f'{TOP}.ext.spice', WORK / 'verify' / f'{TOP}.lvs.spice': f'{TOP}.lvs.spice',
             WORK / 'rc' / f'{TOP}.rc.spice': f'{TOP}.rc.spice'}
    res['sha256'] = {}
    for src, name in files.items():
        if Path(src).exists():
            shutil.copy(src, OUT / name)
            res['sha256'][name] = tools.sha(OUT / name)
            if publish:
                shutil.copy(src, FAST / name)
    for f in ('lvs.txt', 'drc-count.txt', 'antenna.txt', 'verify.json'):
        if (WORK / 'verify' / f).exists():
            shutil.copy(WORK / 'verify' / f, OUT / f'{TOP}-{f}')
    res['pins'] = {k: v for k, v in res['pins'].items()}
    (OUT / 'report.json').write_text(json.dumps(res, indent=1))
    return res


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if what == 'build':                  # layout + DRC / LVS in the build directory only (seconds)
        r, _, _ = build_top()
        r['build_check'] = check(WORK / 'build', TOP, ref_netlist())
        print(json.dumps({k: r[k] for k in ('size_um', 'area_um2', 'build_check')}, indent=1))
    elif what == 'em':                   # python3 wtx_mux8_layout.py em 24.3   -> table for another bank current (no rebuild)
        r = json.loads((OUT / 'report.json').read_text())
        print(json.dumps(em_table(r, float(sys.argv[2])), indent=1))
    else:
        r = run_all()
        v = r['verify_from_disk']
        print(json.dumps(dict(size_um=r['size_um'], area_um2=r['area_um2'], magic_drc=v['magic_drc'], klayout=v['klayout_drc'].get('violations'),
                              lvs=v['lvs']['summary'], negatives={k: x['fails_as_required'] for k, x in v['negative_controls'].items()},
                              antenna=v['antenna_magic'], rc=r['rc_netlist'], c_netlist={k: r['c_netlist'][k] for k in ('vsubs_lines_fixed', 'ports_ok', 'devices', 'floating_vsubs_left')},
                              outputs_fF={n: r['wire_c_fF'][n]['total'] for n in BUS_ORDER}, em_worst=r['em_table']['worst'], sha256=r['sha256']), indent=1))
