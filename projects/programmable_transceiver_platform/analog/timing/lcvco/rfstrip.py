"""Hand-placed RF device strips for the QVCO r5 tank (LO owner, 2026-11-11).

Why not layout_engine: its one-PCell-per-finger rows with private M2/M3 escapes put ~20 ohm of via/escape
R in series with every band MIM and route band-switch nodes on 0.4 um wires (r4 extraction: no start-up
at bands >= 12).  Here a multi-finger device is ONE shared-diffusion strip (fingers vertical) with:
  * per contact column: diffusion contact + Metal1 strip over the full finger height;
  * horizontal in-strip buses (one per drain/source net) on Metal2 || Metal3 over the diffusion, joined to
    every contact column of that net by a via1 column (Metal1 pad) and a via2 column;
  * poly gates contacted outside the diffusion on a poly bar per gate net (bottom bar and/or top bar), the
    bar strapped by Metal1 || Metal2 || Metal3 with a poly contact + via1 + via2 at every finger.
Geometry constants are the ones proven DRC/LVS-clean in compact.py (contact 0.23, contact-to-gate 0.185,
poly end cap 0.22) plus the Magic gf180mcuD via/metal rules (via1 0.26, via2-4 0.28, M2-M4 0.28 min).
Coordinates in microns, snapped to 0.005.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import layout_engine as le  # noqa: E402

CW = 0.23           # diffusion contact width
CG = 0.30           # contact centre to gate edge (0.115 + 0.185)
ENDCAP = 0.22
BAR_OFF = 0.70      # bar centre distance from the diffusion edge
TAP_OFF = 0.95      # tap centre distance from the bar centre (outer side)


def s(v):
    return le.snap(v)


class RF(le.Layout):
    def label(self, net, layer, x, y, port=None):
        self.cmds += [f'box values {s(x - 0.1)} {s(y - 0.1)} {s(x + 0.1)} {s(y + 0.1)}',
                      f'label {net} FreeSans 0.3 0 0 0 c {layer}']
        if port is not None:
            self.cmds.append(f'port make {port}')
        elif getattr(self, 'auto_port', False):
            self.nport = getattr(self, 'nport', 0) + 1
            self.cmds.append(f'port make {self.nport}')

    def varea(self, k, x1, y1, x2, y2):
        """via-k area (Magic generates the cut array); metal k and k+1 must already surround it."""
        self.rect(f'via{k}', x1, y1, x2, y2)

    def stack(self, x1, y1, x2, y2, lo, hi):
        """Metal lo..hi over the same rectangle, joined by via areas inset 0.07 (surround rules)."""
        for m in range(lo, hi + 1):
            self.rect(f'metal{m}', x1, y1, x2, y2)
        for m in range(lo, hi):
            self.varea(m, x1 + 0.07, y1 + 0.07, x2 - 0.07, y2 - 0.07)

    # ------------------------------------------------------------------ multi-finger strip
    def strip(self, x0, y0, W, L, kind, cnets, gnets, bars, buses, taps=None, tapnet=None, wellnet=None,
              bus_top=3):
        """kind 'n' (nfet_03v3), 'p' (pfet_03v3, nwell drawn), 'v' (nvaractor, nwell = contact nets).
        cnets: contact-column nets (len n+1); gnets: gate nets (len n).
        bars: {'bot': net or None, 'top': net or None}; each gate net must be one of them; a net on both
        bars is contacted at both ends.  buses: {net: (ylo, yhi)} relative to y0, in-diffusion Metal2(..bus_top).
        taps: ('bot'/'top'/'both') substrate (n) or well (p) tap rows outside the bars on `tapnet`.
        Returns geometry dict."""
        n = len(gnets)
        assert len(cnets) == n + 1
        pitch = 2 * CG + L
        xc = [s(x0 + i * pitch) for i in range(n + 1)]
        xg = [s(x0 + i * pitch + CG + L / 2) for i in range(n)]
        xl, xr = xc[0] - 0.185, xc[-1] + 0.185
        g = dict(xc=xc, xg=xg, x1=xl, x2=xr, y0=y0, y1=y0 + W, pitch=pitch)
        if kind == 'v':
            self.rect('nsubdiff', xl, y0, xr, y0 + W)
            for x in xg:
                self.rect('nvaractor', x - L / 2, y0, x + L / 2, y0 + W)
            ctype = 'nsubdiffcont'
        else:
            self.rect('ndiff' if kind == 'n' else 'pdiff', xl, y0, xr, y0 + W)
            ctype = 'ndiffc' if kind == 'n' else 'pdiffc'
        for i, x in enumerate(xc):
            self.rect(ctype, x - CW / 2, y0 + 0.065, x + CW / 2, y0 + W - 0.065)
            self.rect('metal1', x - CW / 2, y0, x + CW / 2, y0 + W)
        ybb, ytb = y0 - BAR_OFF, y0 + W + BAR_OFF
        g['ybar'] = {'bot': ybb, 'top': ytb}
        # gates
        for j, (x, net) in enumerate(zip(xg, gnets)):
            ends = [k for k in ('bot', 'top') if bars.get(k) == net]
            if not ends:
                raise ValueError(f'gate {j} net {net} has no bar')
            lo = ybb - 0.18 if 'bot' in ends else y0 - ENDCAP
            hi = ytb + 0.18 if 'top' in ends else y0 + W + ENDCAP
            if kind == 'v':
                self.rect('polysilicon', x - L / 2, lo, x + L / 2, y0)
                self.rect('polysilicon', x - L / 2, y0 + W, x + L / 2, hi)
            else:
                self.rect('polysilicon', x - L / 2, lo, x + L / 2, hi)
        for k, yb in (('bot', ybb), ('top', ytb)):
            net = bars.get(k)
            if not net:
                continue
            gx = [x for x, nn in zip(xg, gnets) if nn == net]
            if not gx:
                continue
            a, b = min(gx) - max(0.18, L / 2), max(gx) + max(0.18, L / 2)
            self.rect('polysilicon', a, yb - 0.18, b, yb + 0.18)
            for x in gx:
                self.rect('polycontact', x - 0.115, yb - 0.115, x + 0.115, yb + 0.115)
            # strap: M1 0.38, M2/M3 0.56 (via1 / via2 per finger)
            self.rect('metal1', a - 0.02, yb - 0.19, b + 0.02, yb + 0.19)
            out = -1 if k == 'bot' else 1
            ym = yb + out * 0.09                       # M2/M3 grow outward (away from the diffusion)
            self.rect('metal2', a - 0.02, ym - 0.28, b + 0.02, ym + 0.28)
            self.rect('metal3', a - 0.02, ym - 0.28, b + 0.02, ym + 0.28)
            for x in gx:
                self.rect('via1', x - 0.13, yb - 0.13, x + 0.13, yb + 0.13)
                self.rect('via2', x - 0.14, ym - 0.14, x + 0.14, ym + 0.14)
            g.setdefault('bars', {})[k] = (net, a - 0.02, ym - 0.28, b + 0.02, ym + 0.28)
        # buses
        g['buses'] = {}
        for net, (blo, bhi) in buses.items():
            cols = [x for x, nn in zip(xc, cnets) if nn == net]
            ya, yb_ = y0 + blo, y0 + bhi
            for x in cols:
                self.rect('metal1', x - 0.19, ya, x + 0.19, yb_)
                self.varea(1, x - 0.13, ya + 0.06, x + 0.13, yb_ - 0.06)
                if bus_top >= 3:
                    self.varea(2, x - 0.14, ya + 0.07, x + 0.14, yb_ - 0.07)
            for m in range(2, bus_top + 1):
                self.rect(f'metal{m}', cols[0] - 0.2, ya, cols[-1] + 0.2, yb_)
            g['buses'][net] = (cols[0] - 0.2, ya, cols[-1] + 0.2, yb_)
        missing = {nn for nn in cnets if nn not in buses}
        if missing:
            raise ValueError(f'contact nets without a bus: {missing}')
        # taps / wells
        g['taps'] = {}
        if taps:
            sides = ('bot', 'top') if taps == 'both' else (taps,)
            for k in sides:
                yt = (ybb - TAP_OFF) if k == 'bot' else (ytb + TAP_OFF)
                if kind == 'p':      # n+ tap 0.6 um past the p+ diffusion ends (KLayout NP.1 slivers at flush ends)
                    self.rect('nsubdiff', xl - 0.6, yt - 0.4, xr + 0.6, yt + 0.4)
                    self.rect('nsubdiffcont', xl + 0.1, yt - 0.115, xr - 0.1, yt + 0.115)
                else:
                    self.rect('psubdiff', xl, yt - 0.25, xr, yt + 0.25)
                    self.rect('psubdiffcont', xl + 0.1, yt - 0.115, xr - 0.1, yt + 0.115)
                self.rect('metal1', xl, yt - 0.3, xr, yt + 0.3)
                g['taps'][k] = (tapnet, xl, yt - 0.3, xr, yt + 0.3)
        if kind == 'p':
            yb0 = (g['taps']['bot'][2] - 0.35) if 'bot' in g['taps'] else ybb - 0.6
            yt0 = (g['taps']['top'][4] + 0.35) if 'top' in g['taps'] else ytb + 0.6
            self.rect('nwell', xl - 1.2, yb0, xr + 1.2, yt0)
            g['well'] = (xl - 1.2, yb0, xr + 1.2, yt0)
        if kind == 'v':
            self.rect('nwell', xl - 0.45, y0 - 0.45, xr + 0.45, y0 + W + 0.45)
            g['well'] = (xl - 0.45, y0 - 0.45, xr + 0.45, y0 + W + 0.45)
        return g


def magic_script(cell, cmds, extra=()):
    return '\n'.join(['crashbackups stop', f'load {cell}', 'units microns', 'snap internal'] + list(cmds) + list(extra)
                     + ['save', 'quit -noprompt']) + '\n'


def drc_script(cell):
    return '\n'.join(['crashbackups stop', f'load {cell}', 'select top cell', 'drc euclidean on', 'drc style drc(full)',
                      'drc check', 'drc catchup', 'set f [open drc-count.txt w]', 'puts $f [drc list count total]',
                      'puts $f [drc listall why]', 'close $f', 'quit -noprompt']) + '\n'
