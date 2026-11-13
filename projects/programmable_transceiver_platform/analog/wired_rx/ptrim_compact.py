"""pt_ptrim compact layout (area pass 4, AP4-1): eight identical channel rows `wp_ch`, placed with timing's
layout_engine.  Same circuit as netlists.ptrim() / ptrim.spice (LVS reference): per channel NAND(PH, ptrim_en) ->
trim node tn with 5 binary groups of [0.6 um switch -> 0.8 x 0.45 um NMOS gate capacitor] -> inverters 2/4, 4/8,
8/16 (the last as two 4/8 fingers).

Row (left to right): bit 0 .. bit 4, each [capacitor fingers on shared VSS diffusion][switch fingers on shared
tc/tn diffusion, tc contact next to the capacitors], then the NAND and the three inverters at the right edge, where the ports leave.  Every channel is
the same cell in the same orientation.

Staging: point FAST / SCRATCH / GEN at a scratch directory (scratch/wired_rx/r9ptrim/stage.py); nothing here
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
CAP_L, CAP_W, SW_W = 0.45, 0.8, 0.6
CAP_SP = 0.0          # extra capacitor gate-to-VSS-contact spacing (0.35 tried: tc-to-VSS went UP, the parasitic is track/poly length)
BIT_ORDER = (0, 1, 2, 3, 4)    # left to right; with the T tracks stacked T4 (lowest) .. T0 no trim-line track runs beside tc0..tc3
CH_PORTS = ['PH', 'EN', 'CKP'] + [f'T{b}' for b in range(5)]
TOP_PORTS = ['VDD_WIRE_SW', 'VSS', 'ptrim_en'] + [f'PH{k}' for k in range(8)] + [f'CKP{k}' for k in range(8)] + \
    [f'T{k}_{b}' for k in range(8) for b in range(5)]


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


def channel():
    c = cap.Cell('wp_ch')
    for b in BIT_ORDER:
        m = 1 << b
        tc, t = f'tc{b}', f'T{b}'
        cols, net = [], []
        for i in range(m):          # capacitor fingers: VSS | tc | VSS ...
            cols += [dict(k='c', n='VSS', p='-'), dict(k='g', net=tc, n=True, p=False, wn=CAP_W, l=CAP_L, sp=CAP_SP)]
            net.append(f'Xc{b}_{i} VSS {tc} VSS VSS nfet_03v3 w={CAP_W:g}u l={CAP_L:g}u')
        cols.append(dict(k='c', n='VSS', p='-'))
        c._add(cols, net)
        cols, net = [], []
        for i in range(m):          # switch fingers, tc contact next to the capacitor group: tc | T | tn | T | tc ...
            cols += [dict(k='c', n=(tc if i % 2 == 0 else 'tn'), p='-'), dict(k='g', net=t, n=True, p=False, wn=SW_W)]
            net.append(f'Xs{b}_{i} {tc} {t} tn VSS nfet_03v3 w={SW_W:g}u l=0.28u')
        cols.append(dict(k='c', n=(tc if m % 2 == 0 else 'tn'), p='-'))
        c._add(cols, net)
    # antenna (KLayout ANT.16_i_ANT.3, Metal2): T0 is one 0.6 um gate at the far left with its track running the whole
    # row; bare N+ diode column (no device, LVS unchanged) on T0 and T1 at the right end, on static nets only
    c.diode('T0')
    c.diode('T1')
    c.nand(['PH', 'EN'], 'tn', 4, 4)
    c.inv('tn', 'ta', 2, 4)
    c.inv('ta', 'tb', 4, 8)
    c.inv('tb', 'CKP', 4, 8)
    c.inv('tb', 'CKP', 4, 8)
    r = Row(c.name, c.cols, ports=CH_PORTS, wn=2, wp=4)
    r.track_order = [f'tc{b}' for b in (4, 3, 2, 1, 0)] + ['tn'] + ['ta', 'tb'] + [f'T{b}' for b in (4, 3, 2, 1, 0)] + ['EN', 'PH', 'CKP']
    return r, CH_PORTS + ['VDD', 'VSS'], c.net


CELLS = dict(wp_ch=channel)


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
                                                           rails=rails, bbox=[0.0, 0.0, round(row.width, 3), round(row.top, 3)]),
                                                      indent=1))
    res.update(size_um=[round(row.width, 2), round(row.top, 2)], area_um2=round(row.width * row.top, 1), devices=len(net))
    return res


def top_netlist():
    txt = f'.subckt pt_ptrim {" ".join(TOP_PORTS)}\n'
    for k in range(8):
        conns = [f'PH{k}', 'ptrim_en', f'CKP{k}'] + [f'T{k}_{b}' for b in range(5)] + ['VDD_WIRE_SW', 'VSS']
        txt += f'XC{k} {" ".join(conns)} wp_ch\n'
    return txt + '.ends pt_ptrim\n'


ROW_GAP = 3.0         # between rows (n-well of row k to the substrate tap of row k+1: 2.45 um)
STRAP_W = 5.0         # VSS / VDD straps (Metal4 + Metal5)


def build_top():
    """Hand-assembled top: eight wp_ch rows stacked in the same orientation; every clock and trim port is the
    row's own Metal2 pin stub extended straight to the right block edge (no trunks: PHk / CKPk wiring is identical
    in every channel); ptrim_en on one vertical Metal3 strap; VSS / VDD on vertical Metal4+Metal5 straps at the
    right end of the rows, where the output inverters are.  LVS against the macro netlist AND against the family
    netlist ptrim.spice (netlists.ptrim())."""
    import wrx_flow as wf
    meta = json.loads((FAST / 'wp_ch.pins.json').read_text())
    pins, rails, bbox = meta['pins'], meta['rails'], meta['bbox']
    ROW_PITCH = round(bbox[3] + ROW_GAP, 2)
    X_EN = round(bbox[2] + 1.6, 2)          # ptrim_en strap, then the VSS and VDD straps
    X_VSS, X_VDD = X_EN + 4.5, X_EN + 11.5
    work = SCRATCH / 'top'
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    shutil.copy(FAST / 'wp_ch.mag', work / 'wp_ch.mag')
    xe = X_VDD + STRAP_W / 2 + 1.0
    top = 7 * ROW_PITCH + bbox[3]
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

    for k in range(8):
        y0 = k * ROW_PITCH
        cmds += ['units microns', f'getcell wp_ch child 0 0 parent 0 {s(y0)}', f'identify XC{k}']
        for pn, (px, py) in pins.items():
            if pn == 'EN':
                rect('metal2', px, y0 + py - 0.2, X_EN + 0.2, y0 + py + 0.2)
                via(X_EN, y0 + py, 2, 3)
                continue
            tp = f'{pn}{k}' if pn in ('PH', 'CKP') else f'T{k}_{pn[1]}'
            rect('metal2', px, y0 + py - 0.2, xe, y0 + py + 0.2)
            port(tp, 'metal2', xe - 0.3, y0 + py)
        for net, xs in (('VSS', X_VSS), ('VDD', X_VDD)):
            yr = y0 + rails[net][1]
            rect('metal1', bbox[2] - 12.0, yr - 0.3, xs + 2.0, yr + 0.3)        # rail extension (overlaps the row rail)
            for m in range(1, 6):
                rect(f'metal{m}', xs - 2.0, yr - 0.6, xs + 2.0, yr + 0.6)
            for dx in (-1.5, -0.5, 0.5, 1.5):
                for dy in (-0.3, 0.3):
                    for m in range(1, 5):
                        h = 0.13 if m == 1 else 0.14
                        rect(f'via{m}', xs + dx - h, yr + dy - h, xs + dx + h, yr + dy + h)
    en_y = [k * ROW_PITCH + pins['EN'][1] for k in range(8)]
    rect('metal3', X_EN - 0.22, en_y[0] - 0.2, X_EN + 0.22, top - 0.5)
    port('ptrim_en', 'metal3', X_EN, top - 0.8)
    for net, xs, tp in (('VSS', X_VSS, 'VSS'), ('VDD', X_VDD, 'VDD_WIRE_SW')):
        for m in (4, 5):
            rect(f'metal{m}', xs - STRAP_W / 2, -0.2, xs + STRAP_W / 2, top + 0.2)
        port(tp, 'metal5', xs, top - 0.5)
    script = ['crashbackups stop', 'load pt_ptrim', 'units microns', 'snap internal'] + cmds + ['save', 'quit -noprompt']
    (work / 'layout.tcl').write_text('\n'.join(script) + '\n')
    (work / 'top.spice').write_text(top_netlist())
    sch = (FAST / 'wp_ch.spice').read_text() + top_netlist()
    res = compact.check(work, 'pt_ptrim', sch)          # Magic DRC, extraction (+C), LVS vs the macro netlist
    shutil.copy(HERE / 'ptrim.spice', work / 'family.spice')
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
    size = [round(xe + 0.3, 2), round(top + 0.6, 2)]       # n-well overhang 0.3 um left, 0.6 um top
    res.update(lvs_family=lvs_fam, gds_export=gx, devices=8 * len(channel()[2]),
               layout=dict(size_um=size, area_um2=round(size[0] * size[1], 1),
                           pin_edge='right (east), Metal2: PHk, CKPk, Tk_0..4 in row k; ptrim_en Metal3 and VSS / VDD_WIRE_SW '
                                    'Metal4+5 straps at the top right',
                           pins={(f'{pn}{k}' if pn in ('PH', 'CKP') else f'T{k}_{pn[1]}'): [round(xe, 2), round(k * ROW_PITCH + py, 2)]
                                 for k in range(8) for pn, (px, py) in pins.items() if pn != 'EN'},
                           straps=dict(ptrim_en=[X_EN, 'metal3'], VSS=[X_VSS, 'metal4+5'], VDD_WIRE_SW=[X_VDD, 'metal4+5']),
                           row_pitch_um=ROW_PITCH))
    (GEN / 'ptrim-compact-report.json').write_text(json.dumps(res, indent=1, default=str))
    return res


def layout_block(ceiling=60000):
    """Full layout flow (cell, top, publishable GDS with block-unique names, KLayout precheck) into GEN;
    writes GEN/ptrim-layout.json with the report keys run_family.layout_block uses."""
    sys.path.insert(0, str(HERE.parent))
    from gds_uniquify import publish_checked
    cell = build_cell()
    top = build_top()
    shutil.copy(SCRATCH / 'top' / 'pt_ptrim.gds', GEN / 'ptrim.gds')
    precheck = publish_checked(GEN / 'ptrim.gds', 'ptrim', 'pt_ptrim')
    ok = bool(top['lvs']['unique_match'] and top['lvs_family']['unique_match'] and cell['lvs']['unique_match'])
    rep = dict(block='ptrim', subckt='pt_ptrim', revision='r9 compact (ptrim_compact.py: 8 x wp_ch rows, hand-assembled top)',
               devices=top['devices'], drc_errors=top['drc_errors'] + cell['drc_errors'], drc_details='',
               lvs_unique_match=ok, lvs_final='Circuits match uniquely.' if ok else 'mismatch',
               lvs_reference='ptrim.spice (netlists.ptrim(), flat) and the wp_ch macro netlist',
               size_um=top['layout']['size_um'], area_um2=top['layout']['area_um2'], area_ceiling_um2=ceiling,
               gds_export=top['gds_export'], klayout_precheck=precheck,
               cells=dict(wp_ch=dict(drc_errors=cell['drc_errors'], lvs_unique=cell['lvs']['unique_match'],
                                     size_um=cell['size_um'], devices=cell['devices'])),
               pin_edge=top['layout']['pin_edge'], pins=top['layout']['pins'], straps=top['layout']['straps'],
               row_pitch_um=top['layout']['row_pitch_um'], extraction='hierarchical (wp_ch subcircuit), cthresh 0, C only')
    (GEN / 'ptrim-layout.json').write_text(json.dumps(rep, indent=1, default=str) + '\n')
    return rep
