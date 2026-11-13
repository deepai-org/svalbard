"""Compact (multi-finger array) layout of the attached TX termination buffer core (PD38, coordinator area request).

Same circuit, devices, sizes and nets as termination_buffer_layout.generate (canonical, 280 single-finger PCells
on a 21 x 26 um grid, 150 x 1051 um). Parallel identical devices (same model, W, L and D/G/S/B nets) become one
nf-finger PCell, strapped by hand (the gf180 PCell does not connect fingers):
  * gate: Metal1 bar over the bottom polycontact row,
  * even diffusion columns (device S side) -> Via1 + Metal2 bar in the upper half of the channel,
    odd columns (D side) -> Via1 + Metal2 bar in the lower half.
Every finger keeps its own W/L, so the extracted device graph equals the canonical one device for device.
Singletons stay single PCells. Pins are routed exactly as the canonical generator does (private M3 riser to a
private M4 lane, M5 net trunk); the same trunk widths and labels are used, so termination_compensation_layout
assembles the compensated buffer from this core unchanged.
    python3 termination_buffer_array_layout.py --output-dir <dir>
"""
import argparse
import hashlib
import json
import math
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from layout import magic, rectangles, terminals
from extract_audit import extracted_graph, export_extracted, key

ROW_W = 132.     # usable placement width (x 6 .. 138), inside the 150 um trunk envelope
LANE = .8


def _cols(r):
    diff = next(k for k in ('mvndiffc', 'ndiffc', 'pdiffc', 'mvpdiffc') if k in r)
    return sorted(r[diff], key=lambda a: a[0])


def strapped(work, name, pcell_cmd, nf, power=False):
    """Build <name> = PCell (nf fingers) + gate bar + S/D bars; return pin points (D, G, S, B) and bbox."""
    (work / f'{name}_p.tcl').write_text('\n'.join([
        'crashbackups stop', 'load workspace', 'units internal', f'set cell [{pcell_cmd}]', 'load $cell',
        f'save {name}_pc', 'quit -noprompt']) + '\n')
    magic(work, f'{name}_p.tcl')
    r = rectangles(work / f'{name}_pc.mag')
    cols = _cols(r)
    if len(cols) != nf + 1:
        raise ValueError(f'{name}: {len(cols)} diffusion columns for nf {nf}')
    xs = [(a[0] + a[2]) / 2 for a in cols]
    y0, y1 = min(a[1] for a in cols), max(a[3] for a in cols)
    pcs = r['polycontact']
    gy0, gy1 = min(a[1] for a in pcs), max(a[3] for a in pcs)
    cmds = ['crashbackups stop', f'load {name}', 'units microns', f'getcell {name}_pc child 0 0 parent 0 0']

    def box(layer, a, b, c, d):
        cmds.extend([f'box values {a:.4f} {b:.4f} {c:.4f} {d:.4f}', f'paint {layer}'])

    def via1(x, ya, yb):
        box('metal1', x - .27, ya - .08, x + .27, yb + .08)
        box('metal2', x - .27, ya - .08, x + .27, yb + .08)
        box('via1', x - .19, ya, x + .19, yb)

    box('metal1', min(a[0] for a in pcs), gy0 - .1, max(a[2] for a in pcs), gy1 + .1)  # gate bar (contains the router's 0.38 um via pad)
    h = y1 - y0
    if power:   # PD38 review: tall bars for the load-current path (strapped to M3/M4 power straps by the router)
        g = max(.05 * h, .25)      # half gap between the bars (>= 0.5 um M2 gap for short fingers, PD42)
        sb, db = (y0 + .5 * h + g, y0 + .95 * h), (y0 + .05 * h, y0 + .5 * h - g)
        sbars, dbars = [sb], [db]
        if h >= 10:   # PD42 EM: S bars top + bottom, D bar centred -> no M1 column segment carries > 0.3 of its current
            sbars, dbars = [(y0 + .05 * h, y0 + .25 * h), (y0 + .75 * h, y0 + .95 * h)], [(y0 + .30 * h, y0 + .70 * h)]
            sb, db = sbars[1], dbars[0]
    else:
        sb = (y0 + .62 * h, y0 + .62 * h + min(2.0, .25 * h))                          # S bar (upper)
        db = (y0 + .38 * h - min(2.0, .25 * h), y0 + .38 * h)                          # D bar (lower)
        sbars, dbars = [sb], [db]
    if min(sb[1] - sb[0], db[1] - db[0]) < .6 or sb[0] - db[1] < .5:
        raise ValueError(f'{name}: device too narrow for S/D strap bars')
    # PD42 (EM at 85 C): the PCell's 0.23 um M1 over each S/D column carried up to 2 finger currents
    # (105-115 % of DRM 14.2 2.09 mA/um at 85 C). Widen every column's M1 to pitch - 0.3 um (<= 0.72 um)
    # over the full contact height; M1 space to the neighbour column stays >= 0.3 um (rule 0.23).
    pitch = min(b - a for a, b in zip(xs, xs[1:]))
    hw = min(.36, (pitch - .3) / 2)
    m1_width = round(2 * hw, 3)
    if hw > .115:
        for k, x in enumerate(xs):   # end columns (one finger, next to the ring's M1) grow inward only
            box('metal1', x - (.115 if k == 0 else hw), y0, x + (.115 if k == len(xs) - 1 else hw), y1)
    for (ya, yb), parity in [(b_, 0) for b_ in sbars] + [(b_, 1) for b_ in dbars]:
        box('metal2', xs[0] - .3, ya, xs[-1] + .3, yb)
        for k, x in enumerate(xs):
            if k % 2 == parity:
                via1(x, ya + .1, yb - .1)
    # PD38 review (latch-up): the PCell ring is contacted on its two vertical sides only; contact the top and
    # bottom strips too, so no channel is more than ~W/2 + 2 um from a contacted tap.
    strip = next(k for k in ('mvpsubdiff', 'psubdiff', 'nsubdiff', 'mvnsubdiff', 'mvnsdiff', 'nsdiff') if k in r)
    cont = {'mvpsubdiff': 'mvpsubdiffcont', 'psubdiff': 'psubdiffcont', 'nsubdiff': 'nsubdiffcont',
            'mvnsubdiff': 'mvnsubdiffcont', 'mvnsdiff': 'mvnsdiffc', 'nsdiff': 'nsdiffc'}[strip]
    hs = [a for a in r[strip] if a[2] - a[0] > 5 * (a[3] - a[1])]
    bottom_strip = min(hs, key=lambda a: a[1])
    for a in hs:
        box(cont, a[0] + .5, a[1] + .065, a[2] - .5, a[3] - .065)   # CO.4 diffusion enclosure
    cmds += ['save', 'quit -noprompt']
    (work / f'{name}.tcl').write_text('\n'.join(cmds) + '\n')
    magic(work, f'{name}.tcl')
    body = next(k for k in ('mvpsubdiffcont', 'psubdiffcont', 'nsubdiffcont', 'mvnsubdiffcont', 'mvnsdiffc', 'nsdiffc', 'nwellc') if k in r)
    bodyrect = max(r[body], key=lambda a: a[2])
    pcx = sorted(((a[0] + a[2]) / 2 for a in pcs))
    gx = pcx[min(5, nf - 1)]                 # nf >= 6: on polycontact 5 (>= 2.5 pitches from the D riser); nf < 6 jogs out (router)
    d_col = 3 if nf >= 4 else 1
    bpin = ((xs[1] + xs[2]) / 2 if nf >= 2 else xs[0], (bottom_strip[1] + bottom_strip[3]) / 2) if power else \
           ((bodyrect[0] + bodyrect[2]) / 2, bodyrect[3] - .2)
    pins = [(xs[d_col], sum(db) / 2), (gx, (gy0 + gy1) / 2), (xs[0], sum(sb) / 2), bpin]
    def m1_fraction(bs):   # uniform contact injection; each contact feeds the nearest bar of its own column
        bs = sorted(bs)
        return max([bs[0][0] - y0, y1 - bs[-1][1]] + [(q[0] - p_[1]) / 2 for p_, q in zip(bs, bs[1:])]) / h
    strap = dict(s=sbars, d=dbars, m1_max_fraction=round(max(m1_fraction(sbars), m1_fraction(dbars)), 3), x0=xs[0] - .3, x1=xs[-1] + .3, m1_column_um=m1_width, pitch_um=round(pitch, 3), w_um=round(h, 3))
    allr = [a for k, v in r.items() if k != 'checkpaint' for a in v]
    bbox = (min(a[0] for a in allr), min(a[1] for a in allr), max(a[2] for a in allr), max(a[3] for a in allr))
    return pins, bbox, strap


def pcell_cmd(model, w, l, nf):
    if model.startswith('ppoly'):
        return f'magic::gencell_makecell gf180mcu::{model} w {w} l {l} guard 1 full_metal 1'
    return (f'magic::gencell_makecell gf180mcu::{model} w {w} l {l} nf {nf} guard 1 topc 0 botc 1 full_metal 1 '
            'gate_to_polycont 0.6 gate_extension 0.8 diff_gate_space 0.3')


POWER_NETS = ('TOP', 'BOTTOM', 'LOCAL_OUT', 'OUT', 'BUFFER_COMPLEMENT_WELL')
SIGNAL_UNITS = set()
# PD42 EM: the tail path (D=TAIL / D=TAIL_RETURN arrays, 0.44 mA tt, 0.89 mA ff at 85 C with the divider bias fixture)
# exceeds one 0.58 mA via cut per pin -> split into 2 arrays, each with its own single-cut pins (<= 0.45 mA).
MIN_CHUNKS = {('TAIL', 'TAIL_RETURN'): 3, ('TAIL_RETURN', 'VSS'): 3, ('LOCAL_OUT', 'TOP'): 2, ('TOP', 'VDD'): 2, ('LOCAL_OUT', 'OUT'): 2, ('OUT', 'VDD'): 4, ('OUT', 'VSS'): 4}   # PD46 EM (85 C, strap-ladder check em_check.py): tails 3 (single-cut pins); tbuf power arrays in 2; steering OUT arrays in 4 (M4 crowding at the trunk entry, review r2); tbuf (LOCAL_OUT,OUT) in 2 (two bars on one trunk, review r3)
# PD42: M5 trunk widths sized from the 85 C EM screen (scratch/pads-pd42/em, <= 4.5 mA/um DRM 14.2 top metal, >= 25 % margin);
# nets not listed keep 8 um.
TRUNK_UM = {'BOTTOM': 3., 'BUFFER_COMPLEMENT_WELL': 4., 'VSS': 4., 'VDD': 11., 'TOP': 11., 'LOCAL_OUT': 11.}


def generate(work, circuit=None, cell_name='buffer_core', power_nets=POWER_NETS, wide_nets=(), trunk_um=None):
    trunk_um = {**TRUNK_UM, **(trunk_um or {})}
    work.mkdir(parents=True, exist_ok=False)
    if circuit is None:
        from design import build_integration_candidate
        circuit = build_integration_candidate('termination_buffer')
    # ---- groups of parallel identical devices -> arrays
    groups = defaultdict(list)
    for d in circuit.devices:
        groups[(d.model, d.w_um, d.l_um, tuple(d.nodes))].append(d)
    units = []                     # (kind key, nodes, names)
    for (model, w, l, nodes), ds in groups.items():
        if model.startswith('ppoly') or len(ds) == 1:
            units += [((model, w, l, 1), nodes, [d.name]) for d in ds]
            continue
        pitch = l + (1.0 if model.endswith('06v0') else .55)
        nmax = max(2, int((ROW_W - 8) / pitch))
        n = len(ds)
        chunks = max(math.ceil(n / nmax), MIN_CHUNKS.get((nodes[0], nodes[2]), 1))
        sizes = [n // chunks + (1 if i < n % chunks else 0) for i in range(chunks)]
        k = 0
        for s in sizes:
            units.append(((model, w, l, s), nodes, [d.name for d in ds[k:k + s]]))
            k += s
    # PD38 review: arrays on the load-current path get tall S/D bars strapped on M3+M4 straight to their M5 trunks
    units = [((m, w, l, nf, bool(nf > 1 and not m.startswith('ppoly') and (nodes[0] in power_nets or nodes[2] in power_nets) and (nodes[0], nodes[2]) not in SIGNAL_UNITS)), nodes, names)
             for (m, w, l, nf), nodes, names in units]
    kinds = sorted({u[0] for u in units}, key=str)
    cells, pins, boxes, straps = {}, {}, {}, {}
    for i, kk in enumerate(kinds):
        model, w, l, nf, power = kk
        name = f'{cell_name}__arr_{i}'
        cells[kk] = name
        if nf == 1:
            (work / f'{name}.tcl').write_text('\n'.join(['crashbackups stop', 'load workspace', 'units internal',
                                                         f'set cell [{pcell_cmd(model, w, l, 1)}]', 'load $cell', f'save {name}', 'quit -noprompt']) + '\n')
            magic(work, f'{name}.tcl')
            pins[kk] = terminals(work / f'{name}.mag')
            r = rectangles(work / f'{name}.mag')
            allr = [a for k2, v in r.items() if k2 != 'checkpaint' for a in v]
            boxes[kk] = (min(a[0] for a in allr), min(a[1] for a in allr), max(a[2] for a in allr), max(a[3] for a in allr))
        else:
            pins[kk], boxes[kk], straps[kk] = strapped(work, name, pcell_cmd(model, w, l, nf), nf, power=power)
    nets = sorted({n for d in circuit.devices for n in d.nodes})
    big = {'VDD', 'VSS'} | set(power_nets) | set(wide_nets)
    order = [n for n in nets if n in big] + [n for n in nets if n not in big]     # wide trunks first in the left bank
    tracks, widths, edge = {}, {}, 2.78
    for net in order:
        width = trunk_um.get(net, 8.) if net in big else .44
        tracks[net] = edge + width / 2; widths[net] = width; edge += width + 1.
    x0 = edge + 2.                                                       # devices right of the trunk bank
    width_w = max(boxes[u[0]][2] - boxes[u[0]][0] for u in units)
    row_w = max(width_w, 80.)
    # ---- placement: power arrays one per row; the rest shelf-packed, widest first
    power_units = [u for u in units if u[0][4]]
    other = sorted([u for u in units if not u[0][4]], key=lambda u: -(boxes[u[0]][2] - boxes[u[0]][0]))
    rows, row, x = [], [], x0
    for u in other:
        bw = boxes[u[0]][2] - boxes[u[0]][0]
        slot = max(bw, 10.) if u[0][3] == 1 else bw     # singles keep the canonical +-2.5/+4 um escapes clear
        if row and (x + slot > x0 + row_w or 4 * (len(row) + 1) * LANE + 2 > 40):
            rows.append(row); row, x = [], x0
        row.append((u, x + (slot - bw) / 2)); x += slot + 2.0
    if row:
        rows.append(row)
    origin = 4.
    placed, y = [], origin
    for u in power_units:                                                 # lanes (G, B) under the cell
        b = boxes[u[0]]
        placed.append(dict(u=u, cx=x0 - b[0], cy=y + 3.2 - b[1], lane0=y + 1, power=True))
        y += 3.2 + (b[3] - b[1]) + 1.5
    for row in rows:
        lanes = 4 * len(row)
        hmax = max(boxes[u[0]][3] - boxes[u[0]][1] for u, _ in row)
        band = max(hmax + 2.5, lanes * LANE + 2.5)
        for j, (u, xx0) in enumerate(row):
            kk = u[0]; b = boxes[kk]
            placed.append(dict(u=u, cx=xx0 - b[0], cy=y + 1.2 - b[1] + (band - 2.5 - (b[3] - b[1])) / 2, lane0=y + 1 + 4 * j * LANE, power=False))
        y += band
    height = y + 6
    commands = ['crashbackups stop', f'load {cell_name}', 'units microns']

    def rect(layer, x1, y1, x2, y2):
        commands.extend([f'box values {min(x1, x2):.4f} {min(y1, y2):.4f} {max(x1, x2):.4f} {max(y1, y2):.4f}', f'paint {layer}'])

    def via(xx, yy, lo, hi):
        for m in range(lo, hi + 1):
            hh = .19 if m == 1 else .22 if m == 5 else .2
            rect(f'metal{m}', xx - hh, yy - hh, xx + hh, yy + hh)
        for m in range(lo, hi):
            hh = .13 if m == 1 else .14; rect(f'via{m}', xx - hh, yy - hh, xx + hh, yy + hh)

    def wire(layer, x1, y1, x2, y2):
        hh = .22 if layer == 'metal5' else .2
        rect(layer, min(x1, x2) - hh, min(y1, y2) - hh, max(x1, x2) + hh, max(y1, y2) + hh)
    access = defaultdict(list)
    lanes_of = lambda p: ({1: 0, 3: 1} if p['power'] else {0: 0, 1: 1, 2: 2, 3: 3})  # noqa: E731
    for p in placed:
        for pin, net in enumerate(p['u'][1]):
            if p['power'] and pin in (0, 2):
                for st in straps[p['u'][0]]['s' if pin == 2 else 'd']:
                    access[net] += [p['cy'] + st[0], p['cy'] + st[1]]
            else:
                access[net].append(p['lane0'] + lanes_of(p)[pin] * LANE)
    spans = {net: ([min(access[net]) - .5, max(access[net]) + .5] if net not in circuit.ports else [origin - .5, height + .5]) for net in nets}
    for net, xx in tracks.items():
        rect('metal5', xx - widths[net] / 2, spans[net][0], xx + widths[net] / 2, spans[net][1])
    strap_report = []
    for i, p in enumerate(placed):
        kk, nodes, names = p['u']
        commands += [f'getcell {cells[kk]} child 0 0 parent {p["cx"]:.4f} {p["cy"]:.4f}', f'identify XU{i}']
        is_res = kk[0].startswith('ppoly')
        for pin, ((dx, dy), net) in enumerate(zip(pins[kk], nodes)):
            xx, yy = p['cx'] + dx, p['cy'] + dy
            if p['power'] and pin in (0, 2):
                st = straps[kk]
                for bar in st['s' if pin == 2 else 'd']:
                    ya, yb = (p['cy'] + v for v in bar)
                    xa, xb = p['cx'] + st['x0'], p['cx'] + st['x1']
                    tl = tracks[net] - widths[net] / 2
                    rect('metal2', tl, ya, xb, yb); rect('metal3', tl, ya, xb, yb); rect('metal4', tl, ya, xb, yb)   # PD42: M2 joins the strap (EM)
                    rect('via2', tl + .3, ya + .3, xb - .3, yb - .3); rect('via3', tl + .3, ya + .3, xb - .3, yb - .3)   # PD46 review: via2/via3 along the whole strap (gap + trunk) so M2+M3+M4 share the strap current
                    rect('via4', tl + .3, ya + .3, tl + widths[net] - .3, yb - .3)
                    strap_report.append(dict(unit=i, net=net, nf=kk[3], model=kk[0], w_um=kk[1], devices=names, m1_column_um=st['m1_column_um'], strap_um=[round(tl, 2), round(ya, 2), round(xb, 2), round(yb, 2)]))
                continue
            ry = p['lane0'] + lanes_of(p)[pin] * LANE
            if kk[3] > 1 and kk[3] < 6 and pin == 1:
                esc = p['cx'] + boxes[kk][2] + 1.0         # small arrays: gate riser outside the cell (M2 jog on the gate bar)
            elif kk[3] > 1:
                esc = xx                                   # array pins are on distinct columns
            else:
                esc = p['cx'] + ((-2.5, 0, 4) if is_res else (2.5, 0, -2.5, 4))[pin]
            via(xx, yy, 1, 2); wire('metal2', xx, yy, esc, yy); via(esc, yy, 2, 3)
            wire('metal3', esc, yy, esc, ry); via(esc, ry, 3, 4)
            wire('metal4', esc, ry, tracks[net], ry); via(tracks[net], ry, 4, 5)
    for net in nets:
        xx = tracks[net]; label_y = height if net in circuit.ports else spans[net][1] - .5
        commands += [f'box values {xx - .2} {label_y - .5} {xx + .2} {label_y}', f'label {net} FreeSans 0.3 0 0 0 c metal5']
        if net in circuit.ports:
            commands += [f'port make {circuit.ports.index(net) + 1}']
    commands += ['select top cell', f'flatten {cell_name}_flat', f'load {cell_name}_flat', 'save', 'select top cell', 'drc check', 'drc catchup',
                 'set f [open drc-count.txt w]', 'puts $f [drc list count total]', 'close $f', 'set f [open drc-details.txt w]',
                 'puts $f [drc listall why]', 'close $f', 'extract all', f'gds write {cell_name}_flat.gds', 'quit -noprompt']
    (work / 'layout.tcl').write_text('\n'.join(commands) + '\n'); magic(work, 'layout.tcl')
    expected = Counter(key(d.model, d.nodes, d.w_um, d.l_um) for d in circuit.devices)
    actual = extracted_graph(work / (cell_name + '_flat.ext'))
    (work / 'schematic.spice').write_text(circuit.spice())
    export_extracted(work / (cell_name + '_flat.ext'), work / 'physical.spice', capacitance=True)
    report = dict(status='compact_array_layout_candidate', circuit=circuit.name, flat_cell=cell_name + '_flat',
                  drc_count=int((work / 'drc-count.txt').read_text()), device_count=len(circuit.devices), placed_units=len(placed),
                  device_graph_matches=actual == expected, envelope_um=[round(x0 + row_w + 2, 2), round(height + 1, 2)], envelope_area_um2=round((x0 + row_w + 2) * (height + 1), 1), power_straps=strap_report,
                  source_sha256={str(f.resolve()): hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__), Path(__file__).with_name('termination_buffer.py'), Path(__file__).with_name('design.py')]})
    if actual != expected:
        report['graph_diff'] = dict(missing=[str(k) for k in (expected - actual)][:10], extra=[str(k) for k in (actual - expected)][:10])
    xs_, ys_ = [], []
    for line in (work / f'{cell_name}_flat.mag').read_text().splitlines():
        if line.startswith('rect '):
            v = [int(q) * .005 for q in line.split()[1:5]]; xs_ += [v[0], v[2]]; ys_ += [v[1], v[3]]
    report['drawn_bbox_um'] = [round(min(xs_), 3), round(min(ys_), 3), round(max(xs_), 3), round(max(ys_), 3)]
    report['drawn_area_um2'] = round((max(xs_) - min(xs_)) * (max(ys_) - min(ys_)), 1)   # authoritative (envelope_um is the placement estimate)
    from gds_markers import repair
    report['gds_marker_repair'] = repair(work, cell_name + '_flat')
    rt = work / 'roundtrip'; rt.mkdir(); shutil.copyfile(work / (cell_name + '_flat.gds'), rt / (cell_name + '_flat.gds'))
    (rt / 'check.tcl').write_text(f'crashbackups stop\ngds read {cell_name}_flat.gds\nload {cell_name}_flat\nselect top cell\nexpand\ndrc check\ndrc catchup\nset f [open drc.txt w]\nputs $f [drc list count total]\nclose $f\nextract all\nquit -noprompt\n')
    magic(rt, 'check.tcl')
    report['gds_roundtrip'] = {'drc_count': int((rt / 'drc.txt').read_text()), 'device_graph_matches': extracted_graph(rt / (cell_name + '_flat.ext')) == actual}
    report['trunk_widths_um'] = widths
    report['units'] = [dict(unit=i, model=p['u'][0][0], w_um=p['u'][0][1], l_um=p['u'][0][2], nf=p['u'][0][3], power=p['u'][0][4], nodes=list(p['u'][1]),
                            devices=p['u'][2], m1_column_um=straps[p['u'][0]]['m1_column_um'] if p['u'][0] in straps else None,
                            pitch_um=straps[p['u'][0]]['pitch_um'] if p['u'][0] in straps else None,
                            m1_max_fraction=straps[p['u'][0]]['m1_max_fraction'] if p['u'][0] in straps else None) for i, p in enumerate(placed)]
    report['physical_sha256'] = hashlib.sha256((work / 'physical.spice').read_bytes()).hexdigest()
    (work / 'layout.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('drc_count', 'device_graph_matches', 'envelope_um', 'envelope_area_um2', 'placed_units', 'gds_roundtrip')}))
    if report['drc_count'] or not report['device_graph_matches'] or report['gds_roundtrip']['drc_count'] or not report['gds_roundtrip']['device_graph_matches']:
        raise ValueError('Array buffer core layout verification failed')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args(); generate(a.output_dir.resolve())
