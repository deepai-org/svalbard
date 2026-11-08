"""Device-level row/channel Magic layout generator for pt_wiredtx.

The hierarchical schematic in cells.py is flattened (depth-first, so devices
of one latch/gate stay adjacent) and placed as PDK MOS gencells in
serpentine rows.  Each row is followed by a routing channel.  Metal layers
are used in fixed directions so that nets can only meet at deliberate vias:

  metal1  device contacts and guard rings (inside the PDK gencells)
  metal2  short horizontal jog from a contact to its private escape column
  metal3  vertical riser from the escape column into the channel above
  metal4  horizontal channel track segments (left-edge packed per channel)
  metal5  vertical trunks joining a net's segments in different channels;
          port trunks run to the top edge, where integration connects.

The approach is an extension of the flat trunk generator in
analog/pads/termination_buffer_layout.py (per-row channels, packed tracks,
free trunk positions).  DRC, LVS and extraction are run by run_wired_tx.sh.
"""
import json
import statistics
from pathlib import Path
import cells as C
import tools

PRIM_GAP = 1.0
ESC_PITCH = 0.9
M4_SIG, M4_PWR = 0.4, 0.8
M5_SIG, M5_PWR = 0.44, 1.6
M4_SPACE = 0.42
M5_SPACE = 0.8
MARGIN = 1.5
SNAP = 0.005
POWER = ('VDD', 'VSS')


def snap(v):
    return round(round(v / SNAP) * SNAP, 4)


class Prim:
    def __init__(self, key, name):
        self.key, self.name = key, name

    def analyse(self, magpath):
        rects, layer = {}, None
        for line in Path(magpath).read_text().splitlines():
            if line.startswith('<< '):
                layer = line[3:-3]
            elif line.startswith('rect ') and layer:
                rects.setdefault(layer, []).append([float(v) * 0.005 for v in line.split()[1:5]])
        allr = [r for k, v in rects.items() if k not in ('checkpaint', 'properties') for r in v]
        self.bbox = (min(r[0] for r in allr), min(r[1] for r in allr),
                     max(r[2] for r in allr), max(r[3] for r in allr))
        diff = next(k for k in ('ndiffc', 'pdiffc') if k in rects)
        body = next(k for k in ('psubdiffcont', 'nsubdiffcont') if k in rects)
        cen = lambda r: ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)
        s = cen(min(rects[diff], key=lambda r: r[0]))
        d = cen(max(rects[diff], key=lambda r: r[2]))
        g = cen(min(rects['polycontact'], key=lambda r: r[1]))
        br = max(rects[body], key=lambda r: r[2])
        b = ((br[0] + br[2]) / 2, br[3] - 0.2)
        self.pins = {'d': d, 'g': g, 's': s, 'b': b}
        gx = g[0]
        esc_s = min(s[0], gx - ESC_PITCH)
        esc_d = max(d[0], gx + ESC_PITCH)
        esc_b = max(b[0], esc_d + ESC_PITCH)
        self.esc = {'s': esc_s, 'g': gx, 'd': esc_d, 'b': esc_b}
        self.x0 = min(self.bbox[0], esc_s - 0.3)
        self.x1 = max(self.bbox[2], esc_b + 0.3)
        self.width = self.x1 - self.x0
        self.height = self.bbox[3] - self.bbox[1]


class MacroPrim:
    """Compact fast cell placed as a child cell: signal pins are Metal2 points
    (reached with via2 only), rails are full-width Metal1 (reached with
    via1+via2 at fixed x near the left edge)."""
    def __init__(self, name):
        meta = json.loads((tools.GENERATED / 'fast' / f'{name}.pins.json').read_text())
        self.key, self.name = (name, 0.0, 0.0), name
        self.bbox = tuple(meta['bbox'])
        self.pinnames = list(meta['ports'])
        self.pins, self.kind = {}, {}
        for n, (x, y) in meta['pins'].items():
            self.pins[n], self.kind[n] = (x, y), 'm2'
        for i, (n, (x, y)) in enumerate(sorted(meta['rails'].items())):
            self.pins[n], self.kind[n] = (0.6 + 1.0 * i, y), 'm1'
        self.esc = {n: v[0] for n, v in self.pins.items()}
        self.x0, self.x1 = self.bbox[0], self.bbox[2]
        self.width = self.x1 - self.x0
        self.height = self.bbox[3] - self.bbox[1]


def pin_names(p):
    return getattr(p, 'pinnames', list('dgsb'))


class Script:
    def __init__(self):
        self.cmd = []

    def rect(self, layer, x1, y1, x2, y2):
        x1, x2 = sorted((snap(x1), snap(x2)))
        y1, y2 = sorted((snap(y1), snap(y2)))
        self.cmd += [f'box values {x1}um {y1}um {x2}um {y2}um', f'paint {layer}']

    def via(self, x, y, lo, hi):
        for m in range(lo, hi + 1):
            h = 0.19 if m == 1 else 0.22 if m == 5 else 0.2
            self.rect(f'metal{m}', x - h, y - h, x + h, y + h)
        for m in range(lo, hi):
            h = 0.13 if m == 1 else 0.14
            self.rect(f'via{m}', x - h, y - h, x + h, y + h)

    def hwire(self, layer, x1, x2, y, w):
        self.rect(layer, min(x1, x2) - w / 2, y - w / 2, max(x1, x2) + w / 2, y + w / 2)

    def vwire(self, layer, x, y1, y2, w):
        self.rect(layer, x - w / 2, min(y1, y2), x + w / 2, max(y1, y2))


def place(cell, prims, row_width, power_trunk_pitch=90.0):
    devs = C.layout_devices(cell)
    # ---- rows (serpentine)
    rows, cur, cw = [], [], 0.0
    for d in devs:
        p = prims[(d.model, d.w, d.l)]
        if cur and cw + PRIM_GAP + p.width > row_width:
            rows.append(cur); cur, cw = [], 0.0
        cur.append(d); cw += (PRIM_GAP if len(cur) > 1 else 0) + p.width
    if cur:
        rows.append(cur)
    x_left = MARGIN + M5_PWR + M5_SPACE  # room for a power trunk at the left edge
    placed, pins = [], []
    for r, row in enumerate(rows):
        widths = [prims[(d.model, d.w, d.l)].width for d in row]
        xs, x = [], x_left
        for w in widths:
            xs.append(x); x += w + PRIM_GAP
        if r % 2:
            total = x - PRIM_GAP
            xs = [x_left + (total - x_left) - (xx - x_left) - w for xx, w in zip(xs, widths)]
        for d, ex in zip(row, xs):
            placed.append((r, d, ex))
    W = max(ex + prims[(d.model, d.w, d.l)].width for _, d, ex in placed) + M5_SPACE + M5_PWR + MARGIN
    nrows = len(rows)
    # ---- nets / trunks
    net_rows, net_x = {}, {}
    for r, d, ex in placed:
        p = prims[(d.model, d.w, d.l)]
        cx = ex - p.x0
        for pn, net in zip(pin_names(p), d.nodes):
            net_rows.setdefault(net, set()).add(r)
            net_x.setdefault(net, []).append(cx + p.esc[pn])
    trunks = []  # (net, x, rlo, rhi_or_top, width)
    taken = []

    def free(x, w, rlo, rhi):
        for (_, tx, tlo, thi, tw) in taken:
            if thi >= rlo and tlo <= rhi and abs(tx - x) < (w + tw) / 2 + M5_SPACE:
                return False
        return MARGIN + w / 2 <= x <= W - MARGIN - w / 2

    def add(net, want, rlo, rhi, w):
        for k in range(0, 4000):
            for x in ((want + k * 0.1, want - k * 0.1) if k else (want,)):
                x = snap(x)
                if free(x, w, rlo, rhi):
                    t = (net, x, rlo, rhi, w); taken.append(t); trunks.append(t); return t
        raise RuntimeError('no trunk position for ' + net)

    top = nrows  # pseudo-row index meaning "to the top edge"
    # power trunks at both edges and on a regular pitch
    for net, off in (('VSS', 0.0), ('VDD', 0.5)):
        xs = [MARGIN + M5_PWR / 2 if net == 'VSS' else W - MARGIN - M5_PWR / 2]
        x = power_trunk_pitch * (1 + off)
        while x < W - power_trunk_pitch / 2:
            xs.append(x); x += power_trunk_pitch
        for x in xs:
            add(net, x, 0, top, M5_PWR)
    order = sorted((n for n in net_rows if n not in POWER),
                   key=lambda n: -(max(net_rows[n]) - min(net_rows[n])))
    for n in order:
        rs = net_rows[n]
        if n in cell.ports or len(rs) > 1:
            rhi = top if n in cell.ports else max(rs)
            add(n, statistics.median(net_x[n]), min(rs), rhi, M5_SIG)
    for n in cell.ports:
        if n not in net_rows:
            raise ValueError('unconnected port ' + n)
    return devs, rows, placed, trunks, W


def generate(work, cell=None, row_width=330.0):
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    cell = cell or C.TOP
    devs = C.layout_devices(cell)
    import shutil
    macros = sorted({d.model for d in devs if isinstance(d, C.MacroDev)})
    keys = sorted({(d.model, d.w, d.l) for d in devs if not isinstance(d, C.MacroDev)})
    prims = {k: Prim(k, f'wtx_p{i}') for i, k in enumerate(keys)}
    s = ['crashbackups stop', 'load workspace']
    for k, p in prims.items():
        model, w, l = k
        s += ['units internal',
              f'set cell [magic::gencell_makecell gf180mcu::{model} w {w} l {l} nf 1 guard 1 topc 0 botc 1 '
              'full_metal 1 gate_to_polycont 0.6 gate_extension 0.8 diff_gate_space 0.3]',
              'load $cell', f'save {p.name}', 'load workspace']
    s.append('quit -noprompt')
    (work / 'prims.tcl').write_text('\n'.join(s) + '\n')
    tools.magic(work, 'prims.tcl')
    for p in prims.values():
        p.analyse(work / f'{p.name}.mag')
    for m in macros:
        shutil.copy(tools.GENERATED / 'fast' / f'{m}.mag', work / f'{m}.mag')
        prims[(m, 0.0, 0.0)] = MacroPrim(m)
    devs, rows, placed, trunks, W = place(cell, prims, row_width)
    sc = Script()
    name = cell.name
    sc.cmd += ['crashbackups stop', f'load {name}', 'units microns', 'snap internal']
    # vertical placement and channel packing
    y = MARGIN
    seg_track = {}
    pin_geo = []
    trunk_by_net = {}
    for t in trunks:
        trunk_by_net.setdefault(t[0], []).append(t)
    row_y = []
    for r, row in enumerate(rows):
        items = [(d, ex) for rr, d, ex in placed if rr == r]
        h = max(prims[(d.model, d.w, d.l)].height for d, _ in items)
        for d, ex in items:
            p = prims[(d.model, d.w, d.l)]
            cx, cy = ex - p.x0, y - p.bbox[1]
            sc.cmd += [f'getcell {p.name} child 0 0 parent {snap(cx)}um {snap(cy)}um',
                       f'identify {d.name.replace("/", "_")}']
            for pn, net in zip(pin_names(p), d.nodes):
                px, py = p.pins[pn]
                pin_geo.append((r, net, cx + p.esc[pn], cy + py, cx + px, getattr(p, 'kind', {}).get(pn, 'm1')))
        row_y.append(y)
        # segments in this channel
        segs = {}
        for g in pin_geo:
            if g[0] == r:
                segs.setdefault(g[1], []).append(g[2])
        for n in list(segs):
            for t in trunk_by_net.get(n, []):
                if t[2] <= r <= t[3]:
                    segs[n].append(t[1])
            if n not in POWER and len(segs[n]) < 2 and n not in trunk_by_net:
                pass
        tracks = []  # list of [right_end, width]
        ybase = y + h + 1.0
        assign = {}
        for n in POWER:
            if n in segs:
                tracks.append([float('inf'), M4_PWR]); assign[n] = len(tracks) - 1
        for n, xs in sorted(((n, xs) for n, xs in segs.items() if n not in POWER), key=lambda a: min(a[1])):
            lo, hi = min(xs) - 0.4, max(xs) + 0.4
            for i, tr in enumerate(tracks):
                if tr[1] == M4_SIG and tr[0] + M4_SPACE < lo:
                    tr[0] = hi; assign[n] = i; break
            else:
                tracks.append([hi, M4_SIG]); assign[n] = len(tracks) - 1
        ty, yy = [], ybase
        for tr in tracks:
            yy += tr[1] / 2; ty.append(yy); yy += tr[1] / 2 + M4_SPACE
        for n, i in assign.items():
            seg_track[(r, n)] = (ty[i], segs[n])
        y = yy + 1.0
    H = y + 1.0
    # routing
    for (r, net, ex, ey, px, kind) in pin_geo:
        sy = seg_track[(r, net)][0]
        if kind == 'm1':
            sc.via(px, ey, 1, 2)
            if abs(px - ex) > 1e-6:
                sc.hwire('metal2', px, ex, ey, 0.4)
        sc.via(ex, ey, 2, 3)
        sc.vwire('metal3', ex, ey, sy, 0.4)
        sc.via(ex, sy, 3, 4)
    trunk_span = {}
    for (r, n), (sy, xs) in seg_track.items():
        w = M4_PWR if n in POWER else M4_SIG
        sc.hwire('metal4', min(xs), max(xs), sy, w)
        for t in trunk_by_net.get(n, []):
            if t[2] <= r <= t[3]:
                sc.via(t[1], sy, 4, 5)
                trunk_span.setdefault(t, []).append(sy)
    labelled = set()
    for (r, n), (sy, xs) in sorted(seg_track.items()):
        if n not in labelled and n not in cell.ports:
            x = min(xs)
            sc.cmd += [f'box values {snap(x-0.15)}um {snap(sy-0.15)}um {snap(x+0.15)}um {snap(sy+0.15)}um',
                       f'label {n.replace("/", "__")} FreeSans 0.2 0 0 0 c metal4']
            labelled.add(n)
    port_done = set()
    for t in trunks:
        n, x, rlo, rhi, w = t
        ys = trunk_span.get(t, [])
        if not ys:
            raise RuntimeError(f'trunk without tracks: {n}')
        lo = min(ys) - 0.3
        hi = H if rhi == len(rows) else max(ys) + 0.3
        sc.vwire('metal5', x, lo, hi, w)
        if n in cell.ports and rhi == len(rows) and n not in port_done:
            port_done.add(n)
            sc.cmd += [f'box values {snap(x-0.2)}um {snap(H-0.6)}um {snap(x+0.2)}um {snap(H)}um',
                       f'label {n} FreeSans 0.3 0 0 0 c metal5',
                       f'port make {cell.ports.index(n)+1}']
    missing = set(cell.ports) - port_done
    if missing:
        raise RuntimeError(f'ports without top trunk: {missing}')
    sc.cmd += ['select top cell', f'save {name}',
               f'gds write {name}.gds',
               f'flatten {name}_flat', f'load {name}_flat', 'select top cell',
               'drc euclidean on', 'drc style drc(full)', 'drc check', 'drc catchup',
               'set f [open drc-count.txt w]', 'puts $f [drc list count total]', 'close $f',
               'set f [open drc-why.txt w]', 'puts $f [drc listall why]', 'close $f',
               f'load {name}', 'select top cell',
               'extract all',
               'ext2spice lvs', f'ext2spice -o {name}_lvs.spice',
               'ext2spice lvs', 'ext2spice cthresh 0', 'ext2spice format ngspice', f'ext2spice -o {name}_pex.spice',
               'quit -noprompt']
    (work / 'cells.tcl').write_text('\n'.join(sc.cmd) + '\n')
    tools.magic(work, 'cells.tcl')
    summary = dict(cell=name, devices=len(devs), rows=len(rows), W_um=round(W, 2), H_um=round(H, 2),
                   area_um2=round(W * H, 1), trunks=len(trunks), row_width_um=row_width,
                   drc_count=int((work / 'drc-count.txt').read_text().split()[0]))
    tools.write_json(work / 'layout-summary.json', summary)
    return summary


if __name__ == '__main__':
    import sys
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else tools.SCRATCH / 'layout'
    rw = float(sys.argv[2]) if len(sys.argv) > 2 else 330.0
    print(json.dumps(generate(work, row_width=rw), indent=1))
