"""wtx8_aux layout generator (control glue, bias switch, two tail DACs wtx_idac2m, CMOS tap; schematic = wtx8_top.aux()).
NOT published.

    python3 wtx8_aux_layout.py            # build, GDS, checks on the GDS read back, extraction -> scratch/wired_tx/s13/mux3/aux

Compact rows compiled with the row compiler of wtx_mux8_layout.py (XRow): one stack of abutted rows with shared rails, every
row WN / WP um high.  Differences to the mux rows:
  * the tracks of a row are solved automatically (solve_tracks: precedence of contact straps and poly-contact pads, then
    interval packing), so the gate list below is the only hand-written part; it mirrors wtx8_top.aux() and cells.idac(),
    device sizes are read from those netlists, LVS checks it;
  * single transistors are N-only / P-only finger groups (gf); a DAC unit is  VDD -PB- S i -PB- VDD ... S i -CB i- BIAS;
  * nets that appear in more than one row are joined by Metal3 columns (Metal4 jog where no common x exists);
  * pins are Metal3 pads over the cell (the parent lands on them from Metal4); VSS is a Metal1 || Metal2 bar on the left
    edge joining every VSS rail, VDD the same on the right edge;
  * the two 15 kohm tap loads are guard-ringed ppolyf_u_1k PCells above the rows.
"""
import json
import re
import shutil
import sys
from pathlib import Path

import cells
import tools
import wtx8_top as T
import wtx_mux8_layout as L
from wtx_mux8_layout import BRK, G, Geo, L0, RAIL_W, XRow, fet, g_inv, g_nand2, g_nor2, nfing, s

CELL = 'wtx8_aux'
WORK = L.WORK / 'aux'
OUT = WORK / 'out'
WN, WP = 5.0, 9.6            # finger width limits of every row (a 19.2 um DAC unit = two PMOS fingers)
HEAD = True                  # the tap's input pair T1 / T2 sits between wtx_mux8's two MAIN load resistors, not in the rows
GAP = 1.0                    # between this cell's right edge (VDD bar) and wtx_mux8's left edge
WA = 66.0                    # row width (7 rows: the cell stays lower than wtx_mux8)


def sizes():
    """{device name: (total width um, length um)} of wtx8_aux's own transistors and of one wtx_idac2m."""
    def tab(text):
        d = {}
        for l in text.splitlines():
            m = re.match(r'X(\w+?)(?:_\d+)? .*fet_03v3 w=([\d.]+)u l=([\d.]+)u', l)
            if m:
                w, ln = d.get(m.group(1), (0.0, float(m.group(3))))
                d[m.group(1)] = (round(w + float(m.group(2)), 4), ln)
        return d
    return tab(T.aux()), tab(cells.IDAC2M.spice())


def gf(pre, kind, d, g, s_, w, l=L0, start='s'):
    """one transistor as an N-only / P-only finger group; start: net of the first contact column ('s' or 'd')."""
    nf = nfing(w, WN if kind == 'n' else WP)
    wf = w / nf
    side = (lambda n: dict(k='c', n=n, p='-')) if kind == 'n' else (lambda n: dict(k='c', n='-', p=n))
    gate = (lambda: G(g, wf, None, p=False, l=l)) if kind == 'n' else (lambda: G(g, None, wf, n=False, l=l))
    a, b = (s_, d) if start == 's' else (d, s_)
    cols = [side(a)]
    for f in range(nf):
        cols += [gate(), side(b if f % 2 == 0 else a)]
    return cols, [fet(f'{pre}_{f}', kind, d, g, s_, wf, l) for f in range(nf)]


def join2(cols, c):
    """as join(), and an N-only group may start on the last contact column of a P-only group (and vice versa)."""
    if not cols:
        cols += c
        return
    a, b = cols[-1], c[0]
    if a == b:
        c = c[1:]
    elif a['k'] == 'c' and b['k'] == 'c' and a.get('n') == '-' and b.get('p') == '-' and a.get('p') != '-':
        cols[-1] = dict(k='c', n=b.get('n'), p=a.get('p'))
        c = c[1:]
    elif a['k'] == 'c' and b['k'] == 'c' and a.get('p') == '-' and b.get('n') == '-' and a.get('n') != '-':
        cols[-1] = dict(k='c', n=a.get('n'), p=b.get('p'))
        c = c[1:]
    else:
        cols.append(BRK)
    cols += c


def solve_tracks(cols, near=2):
    """track index per net of one row.  Rules of XRow's geometry: on a contact column the NMOS net's Metal1 strap runs from the
    diffusion up to its track, the PMOS net's from its track up; a gate's poly-contact pad sits on a neighbouring contact
    column on the gate net's track and must clear both straps.  So: N net < P net on a shared column, N net < gate net < P net
    on the pad column (rail contacts and empty sides do not count).  Then lowest free index over each net's column span."""
    rail = lambda side, n: n in (None, '-') or (side == 'n' and n == 'VSS') or (side == 'p' and n == 'VDD')
    nets, span, less = [], {}, set()

    def see(n, i):
        if n not in span:
            nets.append(n)
            span[n] = [i, i]
        span[n] = [min(span[n][0], i), max(span[n][1], i)]
    for i, c in enumerate(cols):
        if c['k'] == 'c':
            nn, pp = c.get('n'), c.get('p')
            for side, n in (('n', nn), ('p', pp)):
                if not rail(side, n):
                    see(n, i)
            if not rail('n', nn) and not rail('p', pp) and nn != pp:
                less.add((nn, pp))
    for i, c in enumerate(cols):
        if c['k'] != 'g':
            continue
        g, best = c['net'], None
        for j in (i + 1, i - 1):
            if not 0 <= j < len(cols) or cols[j]['k'] != 'c':
                continue
            nn, pp = cols[j].get('n'), cols[j].get('p')
            cons = ([(nn, g)] if not rail('n', nn) else []) + ([(g, pp)] if not rail('p', pp) else [])
            if any(a == b for a, b in cons):
                continue                     # the pad cannot sit on a column that carries its own net's strap
            see(g, j)
            if best is None or len(cons) < len(best):
                best = cons
        if best is None:
            raise ValueError(f'no poly-contact column for gate column {i} ({g})')
        less.update(best)
    tidx, left = {}, list(nets)
    while left:
        ready = [n for n in left if not any(b == n and a in left for a, b in less)]
        if not ready:
            raise ValueError(f'track order cycle among {left[:8]}')
        n = min(ready, key=lambda v: span[v][0])
        t = max([tidx[a] + 1 for a, b in less if b == n] or [0])
        while any(tidx[m] == t and span[n][0] - near <= span[m][1] and span[m][0] - near <= span[n][1] for m in tidx):
            t += 1
        tidx[n] = t
        left.remove(n)
    return tidx


def tap_groups():
    """the CMOS tap without its input pair, for the row beside the MAIN load cluster; listed from the cluster side outwards
    (the row is built right to left): the two skewed inverters first, so TD1 / TD2 end side by side."""
    top, _ = sizes()
    tw = lambda n: top[n][0]
    inv = lambda pre, a, y, wn, wp: g_inv(pre.lower(), a, y, wn, wp, WN, WP)
    g = []
    for x, d_ in (('N', 'TD2'), ('P', 'TD1')):
        g += [gf(f'tk{x}p', 'p', f'TQ{x}', d_, 'VDD', tw(f'TK{x}p'), start='d'), gf(f'tk{x}n', 'n', f'TQ{x}', d_, 'VSS', tw(f'TK{x}n'), top[f'TK{x}n'][1])]
    for x in ('N', 'P'):
        g += [inv(f'TB{x}a', f'TQ{x}', f'TQ{x}B', 1, 2), inv(f'TB{x}b', f'TQ{x}B', f'TAP_{x}', 4, 8)]
    g += [gf('tt', 'n', 'TS', 'ATB_NBIAS', 'TT1', tw('TT'), top['TT'][1]), gf('tts', 'n', 'TT1', 'TEN', 'VSS', tw('TTS'), start='d'),
          g_inv('teni', 'TENB', 'TEN', 1, 2, WN, WP), g_nand2('ten', 'TAP_EN', 'ON', 'TENB', 1, 2, WN, WP)]
    return g[::-1]


def groups():
    """the gate / transistor list of the side cell in placement order (each entry: columns, LVS lines)."""
    top, dac = sizes()
    inv = lambda pre, a, y, wn, wp: g_inv(pre.lower(), a, y, wn, wp, WN, WP)
    nand = lambda pre, a, b, y, wn, wp: g_nand2(pre.lower(), a, b, y, wn, wp, WN, WP)
    nor = lambda pre, a, b, y, wn, wp: g_nor2(pre.lower(), a, b, y, wn, wp, WN, WP)
    tw = lambda n: top[n][0]
    g = []
    # ---- glue (wtx8_top.aux, same order)
    g += [inv('GON', 'ISLAND_OFF', 'ON', 1, 2), inv('GDXB', 'DX', 'DXB', 1, 2), nand('GEX', 'WTX_EXT', 'ON', 'EXTB', 1, 2),
          inv('GEXI', 'EXTB', 'EXT', 4, 8), nor('GENM', 'IDLE', 'EXT', 'ENM0', 1, 4), inv('GENMa', 'ENM0', 'ENM0B', 2, 4),
          inv('GENMb', 'ENM0B', 'ENM', 8, 16), nand('GIM', 'IDLE', 'IDLE_MODE', 'IMB0', 1, 2), nor('GIM2', 'IMB0', 'EXT', 'IMID', 1, 4),
          inv('GIM3', 'IMID', 'IMIDB', 1, 2), nand('GOP', 'EXT', 'DXB', 'OPB', 2, 4), nand('GOP2', 'OPB', 'IMIDB', 'OVP0', 2, 4),
          nand('GON_', 'EXT', 'DX', 'ONB', 2, 4), nand('GON2', 'ONB', 'IMIDB', 'OVN0', 2, 4)]
    for x in ('P', 'N'):
        g += [inv(f'GOV{x}a', f'OV{x}0', f'OV{x}1', 4, 8), inv(f'GOV{x}b', f'OV{x}1', f'OV{x}', 12, 24)]
    g += [nand('GXD', 'DX', 'EXT', 'XDB', 1, 2), inv('GXDI', 'XDB', 'WTX_EXT_DATA', 2, 4),
          nand('GSE', 'SER_EN', 'ON', 'SERB', 1, 2), inv('GSEI', 'SERB', 'SERQ', 2, 4), nand('GEM', 'EN_MAIN', 'ON', 'EMB', 1, 2),
          inv('GEMI', 'EMB', 'ENMAIN_G', 2, 4), nand('GEP', 'EN_POST', 'ON', 'EPB', 1, 2), inv('GEPI', 'EPB', 'ENPOST_G', 2, 4)]
    # ---- bias switch
    g += [nor('GBE', 'ENMAIN_G', 'ENPOST_G', 'BE0', 1, 4), inv('GBT', 'TAP_EN', 'TAPB0', 1, 2), nand('GBE2', 'BE0', 'TAPB0', 'BEN', 1, 2),
          inv('GBE3', 'BEN', 'BENB', 1, 2), gf('bsw', 'n', 'IBIAS', 'BEN', 'ATB_NBIAS', tw('BSW')),
          gf('bd', 'n', 'ATB_NBIAS', 'ATB_NBIAS', 'VSS', tw('BD'), top['BD'][1], start='d'), gf('bpd', 'n', 'ATB_NBIAS', 'BENB', 'VSS', tw('BPD'), start='d')]
    # ---- the two DACs (cells.idac): NB EN ISLAND_OFF C0..C7 BIAS PB
    for tag, en, code, bias, pb in (('dm', 'ENMAIN_G', 'MAIN_CODE', 'MAIN_BIAS', 'ATB_PBIAS'), ('dq', 'ENPOST_G', 'POST_CODE', 'POST_BIAS', 'PBQ')):
        n_ = lambda x: f'{tag}_{x}'
        dw = lambda x: dac[x][0]
        g += [g_inv(n_('ei'), en, n_('ENB'), 1, 2, WN, WP), gf(n_('mn1'), 'n', n_('M1'), 'ATB_NBIAS', 'VSS', dw('MN1'), dac['MN1'][1]),
              gf(n_('swn'), 'n', pb, en, n_('M1'), dw('SWN'), start='s'), gf(n_('mp0'), 'p', pb, pb, 'VDD', dw('MP0'), dac['MP0'][1], start='d'),
              gf(n_('pbu'), 'p', pb, en, 'VDD', dw('PBU'), start='s')]
        for i in range(8):
            nf = nfing(dw(f'MS{i}'), WP)
            uc, un = [], []                  # one unit = one group (inverter, mirror fingers, switch stay in one row)
            for c_, n2 in (g_inv(n_(f'ci{i}'), f'{code}{i}', n_(f'CB{i}'), 1, 2, WN, WP),
                           gf(n_(f'ms{i}'), 'p', n_(f'S{i}'), pb, 'VDD', dw(f'MS{i}'), dac[f'MS{i}'][1], start='s' if nf % 2 else 'd'),
                           gf(n_(f'sw{i}'), 'p', bias, n_(f'CB{i}'), n_(f'S{i}'), dw(f'SW{i}'), start='s')):
                join2(uc, c_)
                un += n2
            g.append((uc, un))
        g += [gf(n_('md'), 'n', bias, bias, 'VSS', dw('MD0') + dw('MD1'), dac['MD0'][1], start='s'), gf(n_('pde'), 'n', bias, n_('ENB'), 'VSS', dw('PDE'), start='s'),
              gf(n_('pdi'), 'n', bias, 'ISLAND_OFF', 'VSS', dw('PDI'), start='s')]
    return g


class Rows(L.RBlock):
    """abutted rows of width W filled with `grp` in order; nets in several rows are linked; `pins` get Metal3 pads;
    `up` nets get a column to above the rows (y = H + 0.8, 1.6, ...); `at` = {net: y} nets get a column reaching y."""

    def __init__(self, W, grp, pins, up=(), at=None, edge=False):
        self.W, self.net = W, []
        rows, cur, curn = [], [], []

        def mk(cols, name):
            # row height from the widest finger actually in the row (a DAC row has 1 um NMOS only)
            wn = max([c.get('wn') or 0 for c in cols if c['k'] == 'g' and c.get('n', True)] + [1.0])
            wp = max([c.get('wp') or 0 for c in cols if c['k'] == 'g' and c.get('p', True)] + [2.0])
            r = XRow(name, cols, wn, wp, min_width=W, tracks=solve_tracks(cols))
            r.build()
            return r
        for c, n in grp:
            trial = list(cur)
            join2(trial, list(c))
            if cur and W and mk(trial, 't').width > W + 1e-6:
                rows.append((cur, curn))
                cur, curn = list(c), list(n)
            else:
                cur, curn = trial, curn + n
        rows.append((cur, curn))
        built = []
        for i, (c, n) in enumerate(rows):
            built.append(mk(c, f'r{i}'))
            self.net += n
        if not W:
            self.W = W = built[0].width
        self.H = self.setup(built, [i % 2 == 1 for i in range(len(built))]) + RAIL_W
        self.nrows = len(built)
        where = {}
        for name, (r, y0, flip) in self.rows.items():
            for n in r.track:
                where.setdefault(n, []).append(name)
        jog = {}

        def link(name, ta, tb):
            try:
                return self.column(name, [ta, tb])
            except RuntimeError:
                pass
            ra = self.rows[ta[0]]
            k = jog.get(ta[0], 0)
            jog[ta[0]] = k + 1
            yj = s(ra[1] + 1.6 + 0.8 * k)
            if yj > ra[1] + ra[0].top - 1.6:
                raise RuntimeError(f'no jog track left in row {ta[0]}')
            self.column(name + '_a', [ta], (yj,))
            self.column(name + '_b', [tb], (yj,))
            xa, xb = self.pin[name + '_a'][0], self.pin[name + '_b'][0]
            self.g.rect('metal4', min(xa, xb) - 0.2, yj - 0.2, max(xa, xb) + 0.2, yj + 0.2)
            self.g.via(xa, yj, 3, 4)
            self.g.via(xb, yj, 3, 4)
            self.pin[name] = self.pin[name + '_a']
        for n in sorted((n for n, v in where.items() if len(v) > 1), key=lambda n: -len(where[n])):
            v = sorted(where[n], key=lambda x: int(x[1:]))
            for a, b in zip(v, v[1:]):
                link(f'{n}@{a}', (a, n), (b, n))
        self.res_y = {}
        for i, n in enumerate(up):
            self.res_y[n] = s(self.H + 0.8 + 0.8 * i)
            self.column(f'{n}@res', [(where[n][-1], n)], (self.res_y[n],))
        for n, y in (at or {}).items():
            self.column(f'{n}@res', [(where[n][0], n)], (y,))
        self.pins = {}
        for n in sorted(pins, key=lambda n: int(where[n][0][1:])):
            row = where[n][0]
            ty = self.ty(row, n)
            if edge:                         # pin on the bottom edge: a column from the net's lowest row down to y = 0
                try:
                    self.column(f'{n}@pin', [(row, n)], (0.2,))
                except RuntimeError:         # no free x under the net: a free column to the edge, joined by a Metal4 jog in that row
                    ra = self.rows[row]
                    k = jog.get(row, 0)
                    jog[row] = k + 1
                    yj = s(ra[1] + 1.6 + 0.8 * k)
                    if yj > ra[1] + ra[0].top - 1.6:
                        raise RuntimeError(f'no jog track left in row {row}')
                    self.column(f'{n}@pa', [(row, n)], (yj,))
                    self.column(f'{n}@pin', [], (0.2, yj))
                    xa, xb = self.pin[f'{n}@pa'][0], self.pin[f'{n}@pin'][0]
                    self.g.rect('metal4', min(xa, xb) - 0.2, yj - 0.2, max(xa, xb) + 0.2, yj + 0.2)
                    self.g.via(xa, yj, 3, 4)
                    self.g.via(xb, yj, 3, 4)
                self.pins[n] = (self.pin[f'{n}@pin'][0], 0.2)
            else:
                self.column(f'{n}@pin', [(row, n)], (s(ty + 0.8),))
                self.pins[n] = (self.pin[f'{n}@pin'][0], s(ty + 0.4))
        self.finish()
        self.rail_m2()
        self.rails = []                      # (y of the VSS rail, y of the VDD rail) per row
        for r, y0, flip in self.rows.values():
            lo, hi = y0, y0 + r.top - RAIL_W
            self.rails.append((hi, lo) if flip else (lo, hi))


LINK = ('ATB_NBIAS', 'ON', 'TAP_EN')     # nets from the side cell to the tap row


def build(work=None):
    work = Path(work or WORK / 'build')
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    mr = json.loads((L.OUT / 'report.json').read_text())
    tp, Hm, Htop = mr['geo']['tap'], mr['slice_um'][1], mr['size_um'][1]
    body_pins = [n for n in T.AUX_PORTS if n not in ('VDD', 'VSS', 'INP', 'INN', 'TAP_P', 'TAP_N')]
    ax, err = None, None
    for w_ in (WA, WA + 1, WA - 1, WA + 2, WA - 2, WA + 3, WA + 4, WA + 6):       # the row split decides whether every net finds its columns
        try:
            ax = Rows(w_, groups(), body_pins, up=LINK, edge=True)
            break
        except (RuntimeError, ValueError) as e:
            err = e
    if ax is None:
        raise err
    W, H = ax.W, ax.H
    ri = L.gen_res(work, {'wtx8_aux_rl': ('ppolyf_u_1k',) + tuple(T.TAP['rl'])})['wtx8_aux_rl']
    x0 = s(W + 1.9 + GAP)                                    # mux x = 0 in this cell's coordinates; this cell's y = the mux's y
    g = Geo()
    g.place(ax.g)
    inst, net = [], list(ax.net)
    ytop = s(H + 3.4)
    # ---- side cell supplies: VSS bar on the left edge, VDD bar on the right edge (Metal1 || Metal2)
    for vss, vdd in ax.rails:
        for m in ('metal1', 'metal2'):
            g.rect(m, -1.6, vss, 0.3, vss + RAIL_W)
            g.rect(m, W - 0.3, vdd, W + 1.9, vdd + RAIL_W)
    for m in ('metal1', 'metal2'):
        g.rect(m, -1.9, 0, -0.9, ytop)
        g.rect(m, W + 0.9, 0, W + 1.9, ytop)
    g.rect('via1', -1.75, 0.3, -1.05, ytop - 0.3)
    g.rect('via1', W + 1.05, 0.3, W + 1.75, ytop - 0.3)
    # ---- tap: input pair between the mux's two MAIN load resistors; TD1 / TS / TD2 leave on Metal4 over the RL bodies, drawn
    #      symmetric about the pair (dummy ends over the other RL), to the tap row in the mux's free top-left corner
    top_ = T.TAP
    xh, sg, yd0, wpair = s(tp['xb'] + x0), tp['sd'], s(tp['yA'] + 4.0), top_['pair'][0]
    yw = {n: s(yd0 + 0.25 + 0.75 * k) for k, n in enumerate(('TD1', 'TS', 'TD2'))}
    ys_ = {n: s(yw['TD2'] + 1.0 + 0.8 * k) for k, n in enumerate(LINK)}
    if yd0 + wpair > tp['y_wire_hi'] + 0.4:
        raise RuntimeError('tap pair does not fit between the RL pads and the TOP plate')
    ty0 = s(Hm + 2.2)                                         # tap row: above the header-gate feeds
    tr = Rows(0.0, tap_groups(), ['TAP_P', 'TAP_N'], at={n: s(v - ty0) for n, v in dict(yw, **ys_).items()})
    xcl = s(mr['clusters']['M'][0] + x0 - (tp['xb'] - mr['clusters']['M'][0]) - mr['loads_um'][0] * 0 - 0.0)
    hw = mr['geo']['nfh'] * 0.44 + 0.6
    xtap = s(tp['xb'] + x0 - hw - 1.3)                        # the cluster's substrate tap strip
    xr = {'TD1': s(xtap - 2.6), 'TD2': s(xtap - 6.4)}         # the two 15 kohm loads, then the row
    tx0 = s(xr['TD2'] - 1.68 - 1.2 - tr.W)
    if ty0 + tr.H > Htop or tx0 < x0 + 2.0:
        raise RuntimeError('tap row does not fit the corner')
    g.place(tr.g, tx0, ty0)
    net += tr.net
    (tvss, tvdd), = tr.rails
    tvss, tvdd = s(tvss + ty0), s(tvdd + ty0)
    yc = s(tvss + RAIL_W + 1.0 + ri['body'] + 1.79)           # ring 1 um above the VSS rail level
    ylo, yhi = s(yc + (ri['c0'][0] + ri['c0'][1]) / 2), s(yc + (ri['c1'][0] + ri['c1'][1]) / 2)
    xe = s(tx0 + tr.W)
    for m in ('metal1', 'metal2'):
        g.rect(m, xe - 0.3, tvss, xr['TD1'] + 1.5, tvss + RAIL_W)        # VSS rail on to the rings
    g.rect('via1', xe, tvss + 0.17, xr['TD1'] + 1.2, tvss + RAIL_W - 0.17)
    g.rect('metal2', xe - 0.3, tvdd, xe + 0.9, tvdd + RAIL_W)            # VDD rail to a Metal2 riser beside the row
    g.rect('metal2', xe + 0.5, min(tvdd, yhi - 0.2), xe + 0.9, max(tvdd + RAIL_W, yhi + 0.2))
    g.rect('metal2', xe + 0.5, yhi - 0.2, xr['TD1'] + 0.2, yhi + 0.2)
    x_end = s(tx0 + min(tr.pin[f'{n}@res'][0] for n in ('TD1', 'TD2')))  # both TD wires end at the same x
    x_far = s(xh + (xh - xtap))
    XFAR_MAX = s(x_far - 1.2)                                     # Metal2 wire ends clear of the mux's ENBM feed (Metal2, 0.8 beyond)
    for i, (n, x) in enumerate(xr.items()):
        inst += [f'getcell wtx8_aux_rl child 0 0 parent {x} {yc}', f'identify XTR{i + 1}']
        g.rect('metal1', x - 1.495, tvss, x - 1.265, yc - ri['py'] - 0.4)     # ring -> VSS rail
        g.rect('metal1', x - ri['hx'], ylo - 0.3, x + ri['hx'], ylo + 0.3)
        g.via(x, ylo, 1, 3)
        g.rect('metal3', x - 0.2, ylo - 0.2, x + 0.2, yw[n] + 0.2)
        g.via(x, yw[n], 2, 3)
        g.rect('metal1', x - ri['hx'], yhi - 0.3, x + ri['hx'], yhi + 0.3)
        g.via(x, yhi, 1, 2)
    net += [f'XTR{i + 1} VDD TD{i + 1} VSS ppolyf_u_1k r_width={top_["rl"][0]}u r_length={top_["rl"][1]}u' for i in range(2)]
    g.rect('ndiff', xh - 0.88 - 0.185, yd0, xh + 0.88 + 0.185, yd0 + wpair)
    for n, dx in (('TD1', sg * 0.88), ('TS', 0.0), ('TD2', -sg * 0.88)):
        x, y = s(xh + dx), yw[n]
        g.rect('ndiffc', x - L.CW / 2, yd0 + 0.065, x + L.CW / 2, yd0 + wpair - 0.065)
        g.rect('metal1', x - L.CW / 2, yd0, x + L.CW / 2, yd0 + wpair)
        g.via(x, y, 1, 2)                 # Metal2 wires (ASM-11a: no aux Metal4 in the block's top band)
        g.label(n, 'metal2', x - 1.5, y)
        xc = s(tx0 + tr.pin[f'{n}@res'][0])
        g.rect('metal2', min(x_end, xc) - 0.2, y - 0.2, min(x_far, XFAR_MAX), y + 0.2)
        g.via(xc, y, 2, 3)
    for pin_, dxg, o in (('INP', sg * 0.44, 'MAIN_P'), ('INN', -sg * 0.44, 'MAIN_N')):
        x, (xl, yl_) = s(xh + dxg), tp['landing'][o]
        xl = s(xl + x0)
        g.rect('polysilicon', x - 0.14, yl_ - 0.18, x + 0.14, yd0 + wpair + 0.22)
        g.rect('polysilicon', min(x, xl) - 0.18, yl_ - 0.18, max(x, xl) + 0.18, yl_ + 0.18)
        g.rect('polycontact', xl - 0.115, yl_ - 0.115, xl + 0.115, yl_ + 0.115)
        g.rect('metal1', xl - 0.19, yl_ - 0.19, xl + 0.19, yl_ + 0.19)
        g.rect('via1', xl - 0.13, yl_ - 0.13, xl + 0.13, yl_ + 0.13)
        g.rect('metal2', xl - 0.2, yl_ - 0.2, xl + 0.2, yl_ + 0.2)
        ax.pins[pin_] = (xl, yl_)
    for sgn in (-1, 1):          # substrate taps on both sides of the pair, strapped (Metal1) onto the top VSS rail of the mux's stack row
        xt = s(xh + sgn * 1.75)
        g.rect('psubdiff', xt - 0.25, yd0, xt + 0.25, yd0 + wpair)
        g.rect('psubdiffcont', xt - 0.115, yd0 + 0.135, xt + 0.115, yd0 + wpair - 0.135)
        g.rect('metal1', xt - 0.2, Hm - 0.7, xt + 0.2, yd0 + wpair)
    net += [fet('t1_0', 'n', 'TD1', 'INP', 'TS', wpair, top_['pair'][1]), fet('t2_0', 'n', 'TD2', 'INN', 'TS', wpair, top_['pair'][1])]
    # ---- the three static nets from the side cell to the tap row: Metal5 up from their columns, Metal4 across the corner
    for n in LINK:
        xa, yr_, y, xc = ax.pin[f'{n}@res'][0], ax.res_y[n], ys_[n], s(tx0 + tr.pin[f'{n}@res'][0])
        g.via(xa, yr_, 3, 5)
        g.rect('metal5', xa - 0.22, yr_ - 0.22, xa + 0.22, y + 0.22)
        g.via(xa, y, 4, 5)
        g.rect('metal4', xa - 0.2, y - 0.2, xc + 0.2, y + 0.2)
        g.via(xc, y, 3, 4)
    # ---- pins
    pins = dict(ax.pins)
    pins.update({n: (s(tx0 + v[0]), s(ty0 + v[1])) for n, v in tr.pins.items()})
    for i, n in enumerate(T.AUX_PORTS):
        if n in ('INP', 'INN'):
            g.label(n, 'metal2', pins[n][0], pins[n][1], i + 1)
        elif n == 'VSS':
            g.label(n, 'metal2', -1.4, 1.0, i + 1)
            g.label(n, 'metal2', tx0 + 1.0, tvss + 0.3, i + 1)
        elif n == 'VDD':
            g.label(n, 'metal2', W + 1.4, 1.0, i + 1)
            g.label(n, 'metal2', tx0 + 1.0, tvdd + 0.3, i + 1)
        else:
            g.label(n, 'metal3', pins[n][0], pins[n][1], i + 1)
    L.run_tcl(work, CELL, g.tcl(CELL, extra=inst))
    size = [s(W + 1.9 + 1.9), ytop]
    res = dict(size_um=size, area_um2=round(size[0] * size[1], 1), rows=ax.nrows, row_height_um=[round(r.top, 2) for r, _, _ in ax.rows.values()],
               tracks=[r.ntracks for r, _, _ in ax.rows.values()], pins={n: ['metal2' if n in ('INP', 'INN') else 'metal3', s(v[0] + 1.9), v[1]] for n, v in pins.items()},
               supply_pins=dict(VSS=[['metal2', 0.5, 1.0], ['metal2', s(tx0 + 2.9), s(tvss + 0.3)]], VDD=[['metal2', s(W + 3.3), 1.0], ['metal2', s(tx0 + 2.9), s(tvdd + 0.3)]]),
               columns=len(ax.cols3), m5_risers_x=[s(ax.pin[f'{n}@res'][0] + 1.9) for n in LINK], side_top_y=ytop,
               tap_row=dict(box_in_mux=[s(tx0 - x0), ty0, s(xr['TD1'] + 1.68 - x0), s(max(ty0 + tr.H, yc + ri['body'] + 1.79))], size_um=[tr.W, round(tr.H, 2)],
                            tracks=[r.ntracks for r, _, _ in tr.rows.values()]),
               head=dict(pair_centre_in_mux=[tp['xb'], s(yd0 + wpair / 2)], mux_origin_in_cell_x=x0, td_wire_um=round(x_far - x_end, 1)),
               origin_note='pin x are from the left edge of the side cell (VSS bar); y = mux y')
    return res, ax


def combo(res):
    """wtx_mux8 and wtx8_aux placed together as in the block (no parent wiring): Magic DRC, KLayout DRC of the exported GDS,
    the nets the two cells share, and the wiring C of MAIN_P / MAIN_N with the tap attached."""
    work = WORK / 'combo'
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    for d in (L.WORK / 'build', WORK / 'build'):
        for f in d.glob('*.mag'):
            shutil.copy(f, work / f.name)
    x0 = res['head']['mux_origin_in_cell_x'] if res.get('head') else s(res['size_um'][0] - 1.9 + GAP)
    name = 'wtx8_combo'
    (work / f'{name}.tcl').write_text('\n'.join(
        ['crashbackups stop', f'load {name}', 'units microns', 'snap internal', f'getcell {CELL} child 0 0 parent 0 0', 'identify XAUX',
         f'getcell {L.TOP} child 0 0 parent {x0} 0', 'identify XMUX', 'save', 'quit -noprompt']) + '\n')
    L.magic(work, f'{name}.tcl')
    chk = L.check(work, name, '', lvs=False)
    out = dict(mux_origin_x_um=x0, magic_drc=chk['drc_errors'])
    lv = (work / f'{name}.lvs.spice').read_text().replace('\n+', ' ')
    sub = {m.group(1): m.group(2).split() for m in re.finditer(r'\.subckt (\S+) (.*)', lv)}
    inst = {}
    for l in lv.splitlines():
        tk = l.split()
        if tk and tk[0].startswith('X') and tk[-1] in (CELL, L.TOP):
            inst[tk[-1]] = dict(zip(sub[tk[-1]], tk[1:-1]))
    if CELL in inst and L.TOP in inst:
        a, m = inst[CELL], inst[L.TOP]
        out['shared_nets'] = sorted(f'{pa}={pm}' for pa, na in a.items() for pm, nm in m.items() if na == nm)
        out['INP_is_MAIN_P'], out['INN_is_MAIN_N'] = a.get('INP') == m.get('MAIN_P'), a.get('INN') == m.get('MAIN_N')
        tot = {}
        for l in (work / f'{name}.ext.spice').read_text().splitlines():
            if l.startswith('C'):
                tk = l.split()
                u = {'f': 1.0, 'p': 1e3, 'a': 1e-3, 'n': 1e6}.get(tk[3][-1])
                v = float(tk[3][:-1]) * u if u else float(tk[3]) * 1e15
                for n in tk[1:3]:
                    tot[n] = tot.get(n, 0.0) + v
        flat = lambda n: next((k for k in (n, f'XMUX/{n}', f'XAUX/{n}') if k in tot), None)
        out['wire_c_with_tap_fF'] = {o: round(tot.get(flat(m[o]) or m[o], 0.0), 1) for o in ('MAIN_P', 'MAIN_N')}
        out['tap_nodes_fF'] = {n: round(tot.get(f'XAUX/{n}', 0.0), 1) for n in ('TD1', 'TD2', 'TS')}
    gds = L.export_gds(work, name)
    k = tools.klayout_drc(work, gds, name)
    out['klayout_drc'] = dict(ran=k.get('ran'), violations=k.get('violations'), by_rule=k.get('by_rule'))
    out['partners_fF'] = {}
    for o in ('MAIN_P', 'MAIN_N'):
        pr = {}
        for l in (work / f'{name}.ext.spice').read_text().splitlines():
            tk = l.split()
            if l.startswith('C') and (flat(m[o]) or m[o]) in tk[1:3]:
                other = tk[2] if tk[1] == (flat(m[o]) or m[o]) else tk[1]
                if other.startswith('XAUX'):
                    u = {'f': 1.0, 'p': 1e3, 'a': 1e-3, 'n': 1e6}.get(tk[3][-1])
                    pr[other] = round(pr.get(other, 0.0) + (float(tk[3][:-1]) * u if u else float(tk[3]) * 1e15), 2)
        out['partners_fF'][o] = dict(sorted(pr.items(), key=lambda kv: -kv[1])[:6])
    for f in list(work.glob('*.ext')) + list(work.glob('*.gds')) + list(work.glob('*.mag')):
        f.unlink()
    shutil.rmtree(work / 'klayout', ignore_errors=True)
    return out


def reference():
    return '* reference: wtx8_top.aux_text() (hierarchical: wtx_inv1, wtx_idac2m, wtx8_aux)\n' + T.aux_text()


def run_all():
    res, ax = build()
    b = WORK / 'build'
    res['build_check'] = L.check(b, CELL, reference())
    if res['build_check']['drc_errors'] != 0 or not res['build_check']['lvs']['unique_match']:
        (WORK / 'build' / 'report.json').write_text(json.dumps(res, indent=1))
        return res
    gds = L.export_gds(b, CELL)
    sch = reference()
    neg = sch.replace('XDACM ATB_NBIAS ENMAIN_G ISLAND_OFF MAIN_CODE0 MAIN_CODE1', 'XDACM ATB_NBIAS ENMAIN_G ISLAND_OFF MAIN_CODE1 MAIN_CODE0', 1)
    neg2 = sch.replace("XGOPna_0 OPB EXT GOP_m", "XGOPna_0 OPB DX GOP_m", 1)
    res['verify_from_disk'] = L.verify(gds, WORK / 'verify', CELL, sch, {'neg_dac_code_bits_swapped': neg, 'neg_glue_input_moved': neg2})
    raw = (WORK / 'verify' / f'{CELL}.ext.spice').read_text()
    fixed, nfix = L.fix_vsubs(raw, CELL)
    (WORK / 'verify' / f'{CELL}.ext.spice').unlink()
    (WORK / 'verify' / f'{CELL}.ext.spice').write_text(fixed)
    res['c_netlist'] = dict(vsubs_lines_fixed=nfix, ports_ok=L.ports_of(fixed, CELL) == list(T.AUX_PORTS),
                            resistor_lines=[l for l in fixed.splitlines() if 'ppolyf' in l])
    res['rc_netlist'] = L.extract_rc(gds, WORK / 'rc', CELL, ports=T.AUX_PORTS)
    tot = {}
    for l in fixed.splitlines():
        if l.startswith('C'):
            tk = l.split()
            u = {'f': 1.0, 'p': 1e3, 'a': 1e-3, 'n': 1e6}.get(tk[3][-1])
            for n in tk[1:3]:
                tot[n] = tot.get(n, 0.0) + (float(tk[3][:-1]) * u if u else float(tk[3]) * 1e15)
    res['wire_c_fF'] = {n: round(tot.get(n, 0.0), 1) for n in ('TD1', 'TD2', 'TS', 'INP', 'INN', 'ATB_NBIAS', 'ATB_PBIAS', 'MAIN_BIAS', 'POST_BIAS',
                                                              'ENM', 'EXT', 'OVP', 'OVN', 'TAP_P', 'TAP_N', 'IBIAS')}
    (OUT.parent / 'pins.json').write_text(json.dumps(dict(cell=CELL, size_um=res['size_um'], pins=res['pins'], head=res['head'],
                                                           note=res['origin_note'] + '; INP / INN: Metal2 pads on the mux landings; VSS / VDD: edge bars'), indent=1))
    res['with_wtx_mux8'] = combo(res)
    OUT.mkdir(parents=True, exist_ok=True)
    res['sha256'] = {}
    for src, name in ((gds, f'{CELL}.gds'), (WORK / 'verify' / f'{CELL}.ext.spice', f'{CELL}.ext.spice'),
                      (WORK / 'verify' / f'{CELL}.lvs.spice', f'{CELL}.lvs.spice'), (WORK / 'rc' / f'{CELL}.rc.spice', f'{CELL}.rc.spice')):
        if Path(src).exists():
            shutil.copy(src, OUT / name)
            shutil.copy(src, L.FAST / name)
            res['sha256'][name] = tools.sha(OUT / name)
    (OUT / 'report.json').write_text(json.dumps(res, indent=1))
    return res


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'geo':
        ax = Aux(float(sys.argv[2]) if len(sys.argv) > 2 else None)
        print(ax.W, ax.H, ax.nrows, [(round(r.top, 2), r.ntracks) for r, _, _ in ax.rows.values()], len(ax.cols3))
    else:
        r = run_all()
        v = r.get('verify_from_disk', {})
        print(json.dumps(dict(size_um=r['size_um'], area_um2=r['area_um2'], rows=r['rows'], tracks=r['tracks'], build_check=r['build_check'],
                              verify={k: (x if k not in ('klayout_drc',) else {kk: x.get(kk) for kk in ('ran', 'violations')}) for k, x in v.items()},
                              c_netlist=r.get('c_netlist'), rc=r.get('rc_netlist'), combo=r.get('with_wtx_mux8'), head=r.get('head'), wire_c=r.get('wire_c_fF'), sha256=r.get('sha256')), indent=1)[:6000])
