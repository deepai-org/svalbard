"""Compact hand-placed row compiler for the timing family's fast cells.

A row is a left-to-right sequence of columns shared by an NMOS strip (bottom)
and a PMOS strip (top), standard-cell style:

  * contact column ('c'): diffusion contact strip on N and/or P (net names), or
    continuous diffusion without contact (None), or no diffusion ('-').
  * gate column ('g'): one poly line; on N, P or both (shared input).

Shared diffusion, no per-device guard rings: substrate/well taps run under the
rails.  Routing is local: Metal1 vertical strips from the contacts, Metal2
horizontal tracks in the N/P gap (one track per signal net), polysilicon gate
lines with a poly contact on a free neighbouring column at the gate's track.
Ports are Metal2 track ends brought to the row edge.  Everything is painted
directly (no PCells), so the extracted parasitics are those of the row itself.

Coordinates in microns.  Units snap to 0.005.
"""
from pathlib import Path
import json

import layout_engine as le

PITCH = 1.3          # column pitch (gate centre to contact centre = PITCH/2)
L = 0.28             # gate length
CW = 0.23            # contact strip width
TRACK_W = 0.4
TRACK_P = 0.75
RAIL_W = 0.6


def s(v):
    return le.snap(v)


class Row:
    def __init__(self, name, cols, rail_n='VSS', rail_p='VDD', tap_n='VSS', tap_p='VDD', ports=(), wn=2.0, wp=4.0):
        """cols: list of dicts {k:'c', n:net|None|'-', p:net|None|'-'} or
        {k:'g', net:..., n:bool, p:bool, wn:float, wp:float}.
        rail_n/rail_p: source rails (may differ from the tap nets)."""
        self.name, self.cols, self.ports = name, cols, list(ports)
        self.rail_n, self.rail_p, self.tap_n, self.tap_p = rail_n, rail_p, tap_n, tap_p
        self.wn, self.wp = wn, wp
        self.cmds = []

    def rect(self, layer, x1, y1, x2, y2):
        x1, x2 = sorted((s(x1), s(x2)))
        y1, y2 = sorted((s(y1), s(y2)))
        self.cmds += [f'box values {x1} {y1} {x2} {y2}', f'paint {layer}']

    def label(self, net, layer, x, y, port_index=None):
        self.cmds += [f'box values {s(x - 0.1)} {s(y - 0.1)} {s(x + 0.1)} {s(y + 0.1)}',
                      f'label {net} FreeSans 0.2 0 0 0 c {layer}']
        if port_index is not None:
            self.cmds.append(f'port make {port_index}')

    def via1(self, x, y):
        self.rect('metal1', x - 0.19, y - 0.19, x + 0.19, y + 0.19)
        self.rect('via1', x - 0.13, y - 0.13, x + 0.13, y + 0.13)
        self.rect('metal2', x - 0.2, y - 0.2, x + 0.2, y + 0.2)

    def build(self):
        """Two passes: the first (uniform pitch) picks the poly-contact columns,
        the second places columns tight (0.42 um gate-contact) except next to a
        poly contact (0.65 um), shrinking diffusion and wiring."""
        self._build(None)
        spots = set(self.spots)
        cols = self.cols
        x = [0.6]
        for i in range(1, len(cols)):
            a, b = cols[i - 1]['k'], cols[i]['k']
            if a == 'g' and b == 'g':
                dx = 0.52
            elif a == 'c' and b == 'c':
                dx = 0.65
            elif (i in spots and b == 'c') or (i - 1 in spots and a == 'c'):
                dx = 0.65
            else:
                dx = 0.44
            x.append(x[-1] + dx)
        self.cmds = []
        return self._build(x)

    def _build(self, xpos):
        cols = self.cols
        x = xpos or [0.6 + i * PITCH / 2 for i in range(len(cols))]
        self.spots = []
        # widths: contact columns adopt the max of neighbouring gate widths
        wn = []
        wp = []
        for i, c in enumerate(cols):
            if c['k'] == 'g':
                wn.append(c.get('wn', self.wn) if c.get('n', True) else 0)
                wp.append(c.get('wp', self.wp) if c.get('p', True) else 0)
            else:
                nb = [cols[j] for j in (i - 1, i + 1) if 0 <= j < len(cols) and cols[j]['k'] == 'g']
                wn.append(max([b.get('wn', self.wn) for b in nb if b.get('n', True)] or [self.wn]))
                wp.append(max([b.get('wp', self.wp) for b in nb if b.get('p', True)] or [self.wp]))
        sep_rail_n = self.rail_n != self.tap_n
        sep_rail_p = self.rail_p != self.tap_p
        y_tapn = 0.3
        y_railn = 1.3 if sep_rail_n else y_tapn
        yn0 = y_railn + RAIL_W / 2 + (1.0 if sep_rail_n else 0.55)   # N diffusion bottom
        wn_max = max(wn)
        yn1 = yn0 + wn_max
        # signal nets -> gap tracks
        nets = []

        def add(n):
            if n and n not in ('-',) and n not in (self.rail_n, self.rail_p, self.tap_n, self.tap_p) and n not in nets:
                nets.append(n)
        for c in cols:
            if c['k'] == 'c':
                add(c.get('n'))
                add(c.get('p'))
            else:
                for k in ('net', 'netn', 'netp'):
                    if c.get(k):
                        add(c[k])
        for p in self.ports:
            add(p)
        # order: N-side drain nets low, P-side high where both appear
        if getattr(self, 'track_order', None):
            nets = [n for n in self.track_order if n in nets] + [n for n in nets if n not in self.track_order]
        track = {}
        y = yn1 + 0.75
        for n in nets:
            track[n] = s(y)
            y += TRACK_P
        gap_top = y - TRACK_P + 0.55
        ynw = gap_top + 0.15                      # nwell bottom edge
        yp0 = max(ynw + 0.45, yn1 + 0.45 + 0.45)  # P diffusion bottom
        wp_max = max(wp)
        yp1 = yp0 + wp_max
        y_railp = yp1 + (1.0 if sep_rail_p else 0.55) + RAIL_W / 2
        y_tapp = y_railp + 1.0 if sep_rail_p else y_railp
        width = x[-1] + 0.6
        top = y_tapp + 0.3
        # rails and taps
        self.rect('metal1', 0, y_tapn - RAIL_W / 2, width, y_tapn + RAIL_W / 2)
        self.rect('psubdiff', 0.45, y_tapn - 0.25, width - 0.45, y_tapn + 0.25)
        self.rect('metal1', 0, y_tapn - RAIL_W / 2, width, y_tapn + RAIL_W / 2)
        self.rect('psubdiffcont', 0.55, y_tapn - 0.115, width - 0.55, y_tapn + 0.115)
        if sep_rail_n:
            self.rect('metal1', 0, y_railn - RAIL_W / 2, width, y_railn + RAIL_W / 2)
        self.rect('nwell', -0.3, ynw, width + 0.3, top + 0.6)
        self.rect('metal1', 0, y_tapp - RAIL_W / 2, width, y_tapp + RAIL_W / 2)
        self.rect('nsubdiff', 0.45, y_tapp - 0.25, width - 0.45, y_tapp + 0.25)
        self.rect('nsubdiffcont', 0.55, y_tapp - 0.115, width - 0.55, y_tapp + 0.115)
        if sep_rail_p:
            self.rect('metal1', 0, y_railp - RAIL_W / 2, width, y_railp + RAIL_W / 2)
        # diffusion islands: consecutive columns that are not '-'
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
                        raise ValueError(f'{self.name}: diffusion island must end on a contact column')
                    core = CW / 2 + 0.07
                    xl = x[i] - (core if i == isl[0] else (x[i] - x[i - 1]) / 2)
                    xr = x[i] + (core if i == isl[-1] else (x[i + 1] - x[i]) / 2)
                    if cols[i]['k'] == 'c':
                        # full height only in the contact core; towards each
                        # neighbouring gate, no taller than that gate (PL.5a)
                        self.rect(layer, x[i] - core, y0, x[i] + core, y0 + ws[i])
                        if i != isl[0]:
                            self.rect(layer, xl, y0, x[i] - core, y0 + min(ws[i], ws[i - 1]))
                        if i != isl[-1]:
                            self.rect(layer, x[i] + core, y0, xr, y0 + min(ws[i], ws[i + 1]))
                        continue
                    self.rect(layer, xl, y0, xr, y0 + ws[i])
        used = {}   # column index -> list of (y1, y2) metal1 occupancy in the gap
        vias = {}   # net -> list of x
        for i, c in enumerate(cols):
            if c['k'] != 'c':
                continue
            for side, ctype, y0, ws, rail_y, rail in (('n', 'ndiffc', yn0, wn, y_railn, self.rail_n),
                                                      ('p', 'pdiffc', yp0, wp, y_railp, self.rail_p)):
                net = c.get(side)
                if net in (None, '-'):
                    continue
                w = ws[i]
                self.rect(ctype, x[i] - CW / 2, y0 + 0.065, x[i] + CW / 2, y0 + w - 0.065)
                self.rect('metal1', x[i] - CW / 2, y0 + 0.0, x[i] + CW / 2, y0 + w)  # CO.6 end overlap
                tap_net = self.tap_n if side == 'n' else self.tap_p
                sep = sep_rail_n if side == 'n' else sep_rail_p
                if net == rail:
                    self.rect('metal1', x[i] - CW / 2, min(rail_y, y0 + 0.07), x[i] + CW / 2, max(rail_y, y0 + w - 0.07))
                elif net == tap_net:
                    ty0 = y_tapn if side == 'n' else y_tapp
                    if not sep:
                        self.rect('metal1', x[i] - CW / 2, min(ty0, y0 + 0.07), x[i] + CW / 2, max(ty0, y0 + w - 0.07))
                    else:
                        # jump over the separate source rail on Metal2
                        yj = (rail_y + RAIL_W / 2 + 0.45) if side == 'n' else (rail_y - RAIL_W / 2 - 0.45)
                        yc = y0 + 0.07 if side == 'n' else y0 + w - 0.07
                        self.rect('metal1', x[i] - CW / 2, min(yj, yc), x[i] + CW / 2, max(yj, yc))
                        self.via1(x[i], yj)
                        self.rect('metal2', x[i] - 0.2, min(yj, ty0), x[i] + 0.2, max(yj, ty0))
                        self.via1(x[i], ty0)
                else:
                    ty = track[net]
                    if side == 'n':
                        self.rect('metal1', x[i] - CW / 2, y0 + 0.07, x[i] + CW / 2, ty)
                        used.setdefault(i, []).append((y0, ty + 0.2))
                    else:
                        self.rect('metal1', x[i] - CW / 2, ty, x[i] + CW / 2, y0 + w - 0.07)
                        used.setdefault(i, []).append((ty - 0.2, y0 + w))
                    self.via1(x[i], ty)
                    vias.setdefault(net, []).append(x[i])
        # gates (a gate column may carry different nets on N and P: netn/netp)
        for i, c in enumerate(cols):
            if c['k'] != 'g':
                continue
            segs = []
            nn = c.get('netn', c.get('net') if c.get('n', True) else None)
            pn = c.get('netp', c.get('net') if c.get('p', True) else None)
            if nn and pn and nn == pn:
                segs.append((nn, yn0 - 0.22, yp0 + wp[i] + 0.22))
            else:
                if nn:
                    segs.append((nn, yn0 - 0.22, track[nn] + 0.2))
                if pn:
                    segs.append((pn, track[pn] - 0.2, yp0 + wp[i] + 0.22))
                if nn and pn and not track[nn] + 0.65 < track[pn]:
                    raise ValueError(f'{self.name}: split gate column {i}: N net {nn} must sit on a lower track than P net {pn}')
            for net, yb, yt in segs:
                self.rect('polysilicon', x[i] - L / 2, yb, x[i] + L / 2, yt)
                ty = track[net]
                spot = None
                reuse = False
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
                self.spots.append(spot)
                self.rect('polysilicon', min(x[i], xc) - 0.18, ty - 0.18, max(x[i], xc) + 0.18, ty + 0.18)
                if reuse:
                    continue
                used.setdefault(('pc', spot), []).append(ty)
                used.setdefault(('pcn', spot), []).append((net, ty))
                self.rect('polycontact', xc - 0.115, ty - 0.115, xc + 0.115, ty + 0.115)
                self.rect('metal1', xc - 0.19, ty - 0.19, xc + 0.19, ty + 0.19)
                self.rect('via1', xc - 0.13, ty - 0.13, xc + 0.13, ty + 0.13)
                self.rect('metal2', xc - 0.2, ty - 0.2, xc + 0.2, ty + 0.2)
                vias.setdefault(net, []).append(xc)
        # tracks and ports (ports extended to the right edge, staggered)
        pins = {}
        for k, n in enumerate(nets):
            xs = vias.get(n, [])
            lo, hi = (min(xs), max(xs)) if xs else (width, width)
            if n in self.ports:
                hi = width + 0.6 + 0.9 * self.ports.index(n)
                pins[n] = (s(hi), track[n])
            if hi > lo:
                self.rect('metal2', lo - 0.2, track[n] - TRACK_W / 2, hi + 0.2, track[n] + TRACK_W / 2)
            if xs:
                self.track_starts = getattr(self, 'track_starts', {})
                self.track_starts[n] = (lo, track[n])
        self.width = width + (0.9 * len(self.ports) + 0.9 if self.ports else 0)
        self.top = top
        self.pins = pins
        self.rails = dict(tap_n=(self.tap_n, y_tapn), rail_n=(self.rail_n, y_railn),
                          rail_p=(self.rail_p, y_railp), tap_p=(self.tap_p, y_tapp))
        return self

    def emit(self, work, port_order):
        """Write layout Tcl with labels; port_order = list of all port names in order."""
        idx = {p: i + 1 for i, p in enumerate(port_order)}
        for n, (px, py) in self.pins.items():
            self.label(n, 'metal2', px, py, idx[n])
        # name internal tracks too, so extracted nodes keep schematic names
        for n, (lo, ty) in getattr(self, 'track_starts', {}).items():
            if n not in self.pins:
                self.label(n, 'metal2', lo, ty)
        done = set()
        for key, (net, yy) in self.rails.items():
            if net in done:
                continue
            done.add(net)
            self.label(net, 'metal1', 0.3, yy, idx.get(net))
        script = ['crashbackups stop', f'load {self.name}', 'units microns', 'snap internal'] + self.cmds + ['save', 'quit -noprompt']
        Path(work).mkdir(parents=True, exist_ok=True)
        (Path(work) / 'layout.tcl').write_text('\n'.join(script) + '\n')


def check(work, cell, schematic_spice_text, image=le.DIGITAL_IMAGE):
    """Run build script, DRC, extraction (+C) and LVS like layout_engine."""
    work = Path(work)
    r0 = le.docker_magic(work, 'layout.tcl', image)
    drc = ['crashbackups stop', f'load {cell}', 'select top cell', 'drc euclidean on', 'drc style drc(full)',
           'drc check', 'drc catchup', 'set f [open drc-count.txt w]', 'puts $f [drc list count total]', 'close $f',
           'set f [open drc-details.txt w]', 'puts $f [drc listall why]', 'close $f', 'quit -noprompt']
    (work / 'drc.tcl').write_text('\n'.join(drc) + '\n')
    le.docker_magic(work, 'drc.tcl', image)
    ext = ['crashbackups stop', f'load {cell}', 'select top cell', 'extract all', 'ext2spice lvs',
           f'ext2spice -o {cell}.lvs.spice', 'ext2spice default', 'ext2spice cthresh 0', f'ext2spice -o {cell}.ext.spice',
           f'gds write {cell}.gds', 'quit -noprompt']
    (work / 'check.tcl').write_text('\n'.join(ext) + '\n')
    le.docker_magic(work, 'check.tcl', image)
    (work / 'schematic.spice').write_text(schematic_spice_text)
    lvs = le.netgen_lvs(work, f'{cell}.lvs.spice', cell, 'schematic.spice', cell)
    raw = (work / 'drc-count.txt').read_text().strip() if (work / 'drc-count.txt').exists() else 'missing'
    return dict(drc_errors=le.drc_errors(raw), lvs=lvs)
