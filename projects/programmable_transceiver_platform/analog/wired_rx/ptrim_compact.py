"""pt_ptrim compact layout (area pass 4, AP4-1, and the r10 redesign for the real clock loads, MW-14): eight channel
rows placed with timing's layout_engine.  Same circuit as netlists.ptrim() / ptrim.spice (LVS reference).

Per channel (r10): NAND(PH, ptrim_en) -> tn -> inv1 -> ta -> inv2 -> tb -> inv3 -> CKP.  The 5-bit binary trim is split
between tn and ta (bit b: NTN[b] units on tn and NTA[b] units on ta, each unit = switch NMOS -> NMOS gate capacitor):
a unit delays the edge that RAISES its node about twice as much as the edge that lowers it (the switch passes only
VDD - Vtn), so with the units on two consecutive (inverted) nodes CKP rise and CKP fall move by the same amount and the
duty cycle does not change with the code.  Channel 0 (cell wp_ch0) carries the capture's main clock (2 x the load of
CKP1..7): its inv1 / inv2 / inv3 have CH0_M times the fingers and its ta units CH0_M (x CH0_TA_K) times the width of channels 1..7 (cell wp_ch), which carry a dummy
gate load on tn equal to the extra inv1 gate of channel 0.

Row (left to right): tn units bit 4 .. bit 0, each [capacitor fingers on shared VSS diffusion][switch fingers on shared
tc/node diffusion], NAND, inv1 (+ dummy), ta units bit 0 .. bit 4, inv2, inv3 at the right edge, where the ports
leave.  Rows are right-aligned in the block.

Staging: point FAST / SCRATCH / GEN at a scratch directory (scratch/wired_rx/r10ptrim/stage.py); nothing here
writes generated/ unless the caller leaves the defaults.
"""
from pathlib import Path
import json
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'timing'))
sys.path.insert(0, str(HERE))
import wrx_compact as compact                     # noqa: E402
import layout_engine as le                        # noqa: E402
import capture as cap                             # noqa: E402  (Cell: NAND / inverter column patterns)

BRK = cap.BRK
FAST = HERE / 'generated' / 'fast'
GEN = HERE / 'generated'
SCRATCH = HERE.parents[3] / 'scratch' / 'wired_rx' / 'ptrim'
FAMILY = HERE / 'ptrim.spice'      # LVS reference (netlists.ptrim()); staging may point it at a scratch copy
CAP_SP = 0.0          # extra capacitor gate-to-VSS-contact spacing (0.35 tried in r9: tc-to-VSS went UP, the parasitic is track/poly length)
# ---- r10 design (keep in step with netlists.ptrim()); finger = (wn, wp) um, count
NAND = (4, 4, 2)                  # per finger: series NMOS wn each, PMOS wp each
INV1 = (4, 8, 1)
INV2 = (4, 8, 3)
INV3 = (4, 8, 8)
CH0_M = 2                         # channel 0: inv1, inv2, inv3 fingers x CH0_M, ta unit widths x CH0_M x CH0_TA_K
CH0_TA_K = 1.0
DUMMY_TN = True                   # channels 1..7: (CH0_M - 1) x inv1 gate as MOS capacitors on tn
# bit b: (units on tn, units on ta, capacitor W um, capacitor L um, switch W um)
UNITS = [(1, 1, 0.36, 0.28, 0.36), (1, 1, 0.65, 0.45, 0.6), (2, 2, 0.65, 0.45, 0.6), (4, 4, 0.65, 0.45, 0.6), (8, 8, 0.65, 0.45, 0.6)]
CH_PORTS = ['PH', 'EN', 'CKP'] + [f'T{b}' for b in range(5)]
TOP_PORTS = ['VDD_WIRE_SW', 'VSS', 'ptrim_en'] + [f'PH{k}' for k in range(8)] + [f'CKP{k}' for k in range(8)] + \
    [f'T{k}_{b}' for k in range(8) for b in range(5)]
S_ = cap.S_


class Row(compact.Row):
    """compact.Row with a per-gate-column length ('l', default compact.L): wider poly line and column spacing."""

    def build(self):
        self._build(None)
        spots = set(self.spots)
        cols = self.cols
        x = [0.6]
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
            g = a if a['k'] == 'g' else b
            if g['k'] == 'g':
                dx += (g.get('l', compact.L) - compact.L) / 2
                dx += g.get('sp', 0.0)          # extra gate-to-contact spacing (less contact-to-gate capacitance)
            x.append(x[-1] + dx)
        self.cmds = []
        return self._build(x)

    def _build(self, xpos):
        self._gx = xpos or [0.6 + i * compact.PITCH / 2 for i in range(len(self.cols))]
        return super()._build(xpos)

    def rect(self, layer, x1, y1, x2, y2):
        if layer == 'polysilicon' and abs(abs(x2 - x1) - compact.L) < 1e-6:      # a gate line
            xc = (x1 + x2) / 2
            i = min(range(len(self._gx)), key=lambda j: abs(self._gx[j] - xc))
            c = self.cols[i]
            if c['k'] == 'g' and abs(self._gx[i] - xc) < 1e-6 and c.get('l'):
                x1, x2 = xc - c['l'] / 2, xc + c['l'] / 2
        super().rect(layer, x1, y1, x2, y2)


def _units(c, node, b, tag, m, cw, cl, sw):
    """m switched capacitor units of bit b on `node`: capacitor fingers VSS | tc | VSS ..., then switch fingers with the
    tc contact next to the capacitors: tc | T | node | T | tc ..."""
    tc, t = f'tc{b}{tag}', f'T{b}'
    cols, net = [], []
    for i in range(m):
        g = dict(k='g', net=tc, n=True, p=False, wn=cw, sp=CAP_SP)
        if abs(cl - compact.L) > 1e-9:
            g['l'] = cl
        cols += [dict(k='c', n='VSS', p='-'), g]
        net.append(f'Xc{b}{tag}_{i} VSS {tc} VSS VSS nfet_03v3 w={cw:g}u l={cl:g}u')
    cols.append(dict(k='c', n='VSS', p='-'))
    c._add(cols, net)
    cols, net = [], []
    for i in range(m):
        cols += [dict(k='c', n=(tc if i % 2 == 0 else node), p='-'), dict(k='g', net=t, n=True, p=False, wn=sw)]
        net.append(f'Xs{b}{tag}_{i} {tc} {t} {node} VSS nfet_03v3 w={sw:g}u l=0.28u')
    cols.append(dict(k='c', n=(tc if m % 2 == 0 else node), p='-'))
    c._add(cols, net)


def channel(ch0=False):
    name = 'wp_ch0' if ch0 else 'wp_ch'
    m0 = CH0_M if ch0 else 1
    c = cap.Cell(name)
    for b in (4, 3, 2, 1, 0):
        ntn, nta, cw, cl, sw = UNITS[b]
        if ntn:
            _units(c, 'tn', b, 'a', ntn, cw, cl, sw)
    # antenna (KLayout ANT.16_i_ANT.3, Metal2): T0 / T1 are small gates with their track running the whole row;
    # bare N+ diode column (no device, LVS unchanged) on static nets only
    c.diode('T0')
    c.diode('T1')
    for _ in range(NAND[2]):
        c.nand(['PH', 'EN'], 'tn', NAND[0], NAND[1])
    for _ in range(INV1[2] * m0):
        c.inv('tn', 'ta', INV1[0], INV1[1])
    if DUMMY_TN and not ch0:
        for i in range(INV1[2] * (CH0_M - 1)):          # dummy inv1 gate: both diffusions on the rails
            c._add([S_, cap.G('tn', INV1[0], INV1[1]), S_],
                   [cap.fet(f'dn{i}', 'VSS', 'tn', 'VSS', 'VSS', INV1[0]), cap.fet(f'dp{i}', 'VDD', 'tn', 'VDD', 'VDD', INV1[1], 'p')])
    for b in (0, 1, 2, 3, 4):
        ntn, nta, cw, cl, sw = UNITS[b]
        if nta:
            k0 = m0 * (CH0_TA_K[b] if isinstance(CH0_TA_K, (list, tuple)) else CH0_TA_K) if ch0 else 1          # channel 0: wider ta units (same count)
            _units(c, 'ta', b, 'b', nta, round(cw * k0, 3), cl, round(sw * k0, 3))
    for _ in range(INV2[2] * m0):
        c.inv('ta', 'tb', INV2[0], INV2[1])
    for _ in range(INV3[2] * m0):
        c.inv('tb', 'CKP', INV3[0], INV3[1])
    r = Row(c.name, c.cols, ports=CH_PORTS, wn=2, wp=4)
    r.track_order = [f'tc{b}a' for b in (4, 3, 2, 1, 0)] + [f'tc{b}b' for b in (0, 1, 2, 3, 4)] + ['tn', 'ta', 'tb'] + \
        [f'T{b}' for b in (4, 3, 2, 1, 0)] + ['EN', 'PH', 'CKP']
    return r, CH_PORTS + ['VDD', 'VSS'], c.net


CELLS = dict(wp_ch=lambda: channel(False), wp_ch0=lambda: channel(True))


def subckt(name, ports, net):
    return f'.subckt {name} {" ".join(ports)}\n' + '\n'.join(net) + f'\n.ends {name}\n'


def build_cell(name='wp_ch'):
    row, ports, net = CELLS[name]()
    row.build()
    work = SCRATCH / 'cells' / name
    if work.exists():
        shutil.rmtree(work)
    row.emit(work, ports)
    sch = subckt(name, ports, net)
    res = compact.check(work, name, sch)
    FAST.mkdir(parents=True, exist_ok=True)
    for suf in ('.mag', '.ext.spice', '.lvs.spice', '.gds'):
        f = work / f'{name}{suf}'
        if f.exists():
            shutil.copy(f, FAST / f'{name}{suf}')
    (FAST / f'{name}.spice').write_text('* SPDX-License-Identifier: Apache-2.0\n* generated by ptrim_compact.py (intended netlist)\n' + sch)
    rails = {}
    for key, (net_, yy) in row.rails.items():
        rails.setdefault(net_, [0.3, yy])
    (FAST / f'{name}.pins.json').write_text(json.dumps(dict(ports=ports, pins={k: list(v) for k, v in row.pins.items()},
                                                           rails=rails, bbox=[0.0, 0.0, round(row.width, 3), round(row.top, 3)],
                                                           tracks={k: list(v) for k, v in getattr(row, 'track_starts', {}).items()}),
                                                      indent=1))
    res.update(size_um=[round(row.width, 2), round(row.top, 2)], area_um2=round(row.width * row.top, 1), devices=len(net))
    return res


def cell_of(k):
    return 'wp_ch0' if k == 0 and CH0_M > 1 else 'wp_ch'


def top_netlist():
    txt = f'.subckt pt_ptrim {" ".join(TOP_PORTS)}\n'
    for k in range(8):
        conns = [f'PH{k}', 'ptrim_en', f'CKP{k}'] + [f'T{k}_{b}' for b in range(5)] + ['VDD_WIRE_SW', 'VSS']
        txt += f'XC{k} {" ".join(conns)} {cell_of(k)}\n'
    return txt + '.ends pt_ptrim\n'


ROW_GAP = 3.0         # between rows (n-well of row k to the substrate tap of row k+1: 2.45 um)
STRAP_W = 5.0         # VSS / VDD straps (Metal4 + Metal5)
CKP_W = 1.0           # CKPk Metal2 stub width from the row pin to the block edge
CKP_W3 = 2.0          # CKPk Metal3 strap over the row's own Metal2 CKP track (output fingers -> block edge), via2 every 1 um
RAIL_W23 = 1.6        # Metal2 + Metal3 reinforcement of the row rails from the inv2 / inv3 fingers to the power straps
# EM (85 C, DRM 14.2 as used in spec/power-delivery.md: Metal1-4 2.09 mA/um, via 0.58 mA/cut): a channel draws up to
# ~3 mA (channel 0 ~6 mA) at 810 MHz / ff from each rail; Metal1 0.6 um alone would carry 5-10 mA/um.


def build_top():
    """Hand-assembled top: eight channel rows (row 0 = wp_ch0, rows 1..7 = wp_ch) stacked in the same orientation and
    RIGHT-aligned; every clock and trim port is the row's own Metal2 pin stub extended straight to the right block
    edge (no trunks: PHk / CKPk wiring is identical in channels 1..7); ptrim_en on one vertical Metal4 strap; CKPk additionally on a Metal3 strap; row rails reinforced on Metal2+3; VSS / VDD on
    vertical Metal4+Metal5 straps at the right end of the rows, where the output inverters are.  LVS against the macro
    netlist AND against the family netlist ptrim.spice (netlists.ptrim())."""
    import wrx_flow as wf
    cells = sorted({cell_of(k) for k in range(8)})
    meta = {c: json.loads((FAST / f'{c}.pins.json').read_text()) for c in cells}
    wmax = max(m['bbox'][2] for m in meta.values())
    hrow = max(m['bbox'][3] for m in meta.values())
    for c in cells:          # same rails and pin heights in both cells (same track order): the straps assume it
        assert meta[c]['bbox'][3] == hrow and meta[c]['rails'] == meta[cells[0]]['rails'], 'row cells differ in height / rails'
        assert all(abs(meta[c]['pins'][pn][1] - meta[cells[0]]['pins'][pn][1]) < 1e-6 for pn in meta[c]['pins']), 'pin heights differ'
        assert all(abs((wmax - meta[c]['bbox'][2]) + meta[c]['pins'][pn][0] - meta[cells[0]]['pins'][pn][0]
                       - (wmax - meta[cells[0]]['bbox'][2])) < 1e-6 for pn in meta[c]['pins']), 'pin x differ after right alignment'
    rails = meta[cells[0]]['rails']
    ROW_PITCH = round(hrow + ROW_GAP, 2)
    X_EN = round(wmax + 1.6, 2)          # ptrim_en strap, then the VSS and VDD straps
    X_VSS, X_VDD = X_EN + 4.5, X_EN + 11.5
    work = SCRATCH / 'top'
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    for c in cells:
        shutil.copy(FAST / f'{c}.mag', work / f'{c}.mag')
    xe = X_VDD + STRAP_W / 2 + 1.0
    top = 7 * ROW_PITCH + hrow
    s = le.snap
    cmds = []

    def rect(layer, x1, y1, x2, y2):
        cmds.extend([f'box values {s(min(x1, x2))} {s(min(y1, y2))} {s(max(x1, x2))} {s(max(y1, y2))}', f'paint {layer}'])

    def via(x, y, lo, hi):          # layout_engine.Layout.via geometry
        for m in range(lo, hi + 1):
            h = 0.19 if m == 1 else 0.22 if m == 5 else 0.2
            rect(f'metal{m}', x - h, y - h, x + h, y + h)
        for m in range(lo, hi):
            h = 0.13 if m == 1 else 0.14
            rect(f'via{m}', x - h, y - h, x + h, y + h)

    idx = {p: i + 1 for i, p in enumerate(TOP_PORTS)}

    def port(name, layer, x, y):
        cmds.extend([f'box values {s(x - 0.1)} {s(y - 0.1)} {s(x + 0.1)} {s(y + 0.1)}',
                     f'label {name} FreeSans 0.3 0 0 0 c {layer}', f'port make {idx[name]}'])

    pin_xy = {}
    xleft = {}
    for k in range(8):
        y0 = k * ROW_PITCH
        m = meta[cell_of(k)]
        x0 = s(wmax - m['bbox'][2])
        xleft[k] = x0
        cmds += ['units microns', f'getcell {cell_of(k)} child 0 0 parent {x0} {s(y0)}', f'identify XC{k}']
        for pn, (px, py) in m['pins'].items():
            px += x0
            if pn == 'EN':
                rect('metal2', px, y0 + py - 0.2, X_EN + 0.2, y0 + py + 0.2)
                via(X_EN, y0 + py, 2, 4)
                continue
            tp = f'{pn}{k}' if pn in ('PH', 'CKP') else f'T{k}_{pn[1]}'
            hw = CKP_W / 2 if pn == 'CKP' else 0.2
            rect('metal2', px, y0 + py - hw, xe, y0 + py + hw)
            if pn == 'CKP':          # Metal3 strap over the in-row Metal2 track and the stub
                xa = x0 + m['tracks']['CKP'][0]
                rect('metal3', xa - 0.3, y0 + py - CKP_W3 / 2, xe, y0 + py + CKP_W3 / 2)
                xv = xa
                while xv <= xe - 0.6:
                    rect('via2', xv - 0.14, y0 + py - 0.14, xv + 0.14, y0 + py + 0.14)
                    xv += 1.0
                port(tp, 'metal3', xe - 0.3, y0 + py)
            else:
                port(tp, 'metal2', xe - 0.3, y0 + py)
            pin_xy[tp] = [round(xe, 2), round(y0 + py, 2)]
        for net, xs in (('VSS', X_VSS), ('VDD', X_VDD)):
            yr = y0 + rails[net][1]
            rect('metal1', wmax - 12.0, yr - 0.3, xs + 2.0, yr + 0.3)        # rail extension (overlaps the row rail)
            xa = x0 + m['tracks']['tb'][0] - 1.0                             # reinforcement from the inv2 fingers on
            for mm in (2, 3):
                rect(f'metal{mm}', xa - 0.3, yr - RAIL_W23 / 2, xs + 2.0, yr + RAIL_W23 / 2)
            xv = xa
            while xv <= xs - 2.4:
                rect('via1', xv - 0.13, yr - 0.13, xv + 0.13, yr + 0.13)
                rect('via2', xv - 0.14, yr - 0.14, xv + 0.14, yr + 0.14)
                xv += 1.0
            for mm in range(1, 6):
                rect(f'metal{mm}', xs - 2.0, yr - 0.6, xs + 2.0, yr + 0.6)
            for dx in (-1.55, -0.93, -0.31, 0.31, 0.93, 1.55):
                for dy in (-0.3, 0.3):
                    for mm in range(1, 5):
                        h = 0.13 if mm == 1 else 0.14
                        rect(f'via{mm}', xs + dx - h, yr + dy - h, xs + dx + h, yr + dy + h)
    en_y = [k * ROW_PITCH + meta[cell_of(k)]['pins']['EN'][1] for k in range(8)]
    rect('metal4', X_EN - 0.22, en_y[0] - 0.2, X_EN + 0.22, top - 0.5)      # Metal4: the CKP Metal3 straps cross it
    port('ptrim_en', 'metal4', X_EN, top - 0.8)
    for net, xs, tp in (('VSS', X_VSS, 'VSS'), ('VDD', X_VDD, 'VDD_WIRE_SW')):
        for mm in (4, 5):
            rect(f'metal{mm}', xs - STRAP_W / 2, -0.2, xs + STRAP_W / 2, top + 0.2)
        port(tp, 'metal5', xs, top - 0.5)
    script = ['crashbackups stop', 'load pt_ptrim', 'units microns', 'snap internal'] + cmds + ['save', 'quit -noprompt']
    (work / 'layout.tcl').write_text('\n'.join(script) + '\n')
    (work / 'top.spice').write_text(top_netlist())
    sch = ''.join((FAST / f'{c}.spice').read_text() for c in cells) + top_netlist()
    res = compact.check(work, 'pt_ptrim', sch)          # Magic DRC, extraction (+C), LVS vs the macro netlist
    shutil.copy(FAMILY, work / 'family.spice')
    lvs_fam = le.netgen_lvs(work, 'pt_ptrim.lvs.spice', 'pt_ptrim', 'family.spice', 'pt_ptrim', out='lvs-family.txt')
    GEN.mkdir(parents=True, exist_ok=True)
    for suf in ('.mag', '.ext.spice', '.lvs.spice'):
        f = work / f'pt_ptrim{suf}'
        if f.exists():
            shutil.copy(f, GEN / f'ptrim{suf}')
    try:
        gx = wf.export_gds(work, 'pt_ptrim', 0)
    except Exception as exc:
        gx = dict(error=repr(exc)[:300])
    size = [round(xe + 0.3 + 0.3, 2), round(top + 0.6, 2)]       # n-well overhang 0.3 um left, 0.6 um top
    ndev = sum(len(CELLS[cell_of(k)]()[2]) for k in range(8))
    res.update(lvs_family=lvs_fam, gds_export=gx, devices=ndev,
               layout=dict(size_um=size, area_um2=round(size[0] * size[1], 1),
                           pin_edge='right (east): PHk and Tk_0..4 Metal2, CKPk Metal3 (2 um wide, over a 1 um Metal2 stub) in row k; '
                                    'ptrim_en Metal4 strap and VSS / VDD_WIRE_SW Metal4+5 straps at the top right',
                           pins=pin_xy, row_x0=xleft,
                           straps=dict(ptrim_en=[X_EN, 'metal4'], VSS=[X_VSS, 'metal4+5'], VDD_WIRE_SW=[X_VDD, 'metal4+5']),
                           row_pitch_um=ROW_PITCH))
    (GEN / 'ptrim-compact-report.json').write_text(json.dumps(res, indent=1, default=str))
    return res


def layout_block(ceiling=60000):
    """Full layout flow (cell, top, publishable GDS with block-unique names, KLayout precheck) into GEN;
    writes GEN/ptrim-layout.json with the report keys run_family.layout_block uses."""
    sys.path.insert(0, str(HERE.parent))
    from gds_uniquify import publish_checked
    cells = {c: build_cell(c) for c in sorted({cell_of(k) for k in range(8)})}
    top = build_top()
    shutil.copy(SCRATCH / 'top' / 'pt_ptrim.gds', GEN / 'ptrim.gds')
    precheck = publish_checked(GEN / 'ptrim.gds', 'ptrim', 'pt_ptrim')
    ok = bool(top['lvs']['unique_match'] and top['lvs_family']['unique_match'] and all(c['lvs']['unique_match'] for c in cells.values()))
    rep = dict(block='ptrim', subckt='pt_ptrim', revision='r10 (ptrim_compact.py: wp_ch0 + 7 x wp_ch rows, hand-assembled top)',
               devices=top['devices'], drc_errors=top['drc_errors'] + sum(c['drc_errors'] for c in cells.values()), drc_details='',
               lvs_unique_match=ok, lvs_final='Circuits match uniquely.' if ok else 'mismatch',
               lvs_reference='ptrim.spice (netlists.ptrim(), flat) and the wp_ch0 / wp_ch macro netlists',
               size_um=top['layout']['size_um'], area_um2=top['layout']['area_um2'], area_ceiling_um2=ceiling,
               gds_export=top['gds_export'], klayout_precheck=precheck,
               cells={n: dict(drc_errors=c['drc_errors'], lvs_unique=c['lvs']['unique_match'], size_um=c['size_um'],
                                 devices=c['devices']) for n, c in cells.items()},
               pin_edge=top['layout']['pin_edge'], pins=top['layout']['pins'], straps=top['layout']['straps'],
               row_pitch_um=top['layout']['row_pitch_um'], extraction='hierarchical (wp_ch subcircuit), cthresh 0, C only')
    (GEN / 'ptrim-layout.json').write_text(json.dumps(rep, indent=1, default=str) + '\n')
    return rep
