"""Shared KLayout helpers: GF180 layers, via arrays, metal/via connectivity tracing
and the shared debug-protection bus builder (used by kl_assemble.py and kl_checks.py)."""
import klayout.db as db

LAYERS = {'M1': (34, 0), 'V1': (35, 0), 'M2': (36, 0), 'V2': (38, 0), 'M3': (42, 0), 'V3': (40, 0),
          'M4': (46, 0), 'V4': (41, 0), 'M5': (81, 0)}
L = LAYERS
METALS = ('M1', 'M2', 'M3', 'M4', 'M5')
CONN = (('M1', 'V1', 'M2'), ('M2', 'V2', 'M3'), ('M3', 'V3', 'M4'), ('M4', 'V4', 'M5'))
LABEL_METAL = {34: 'M1', 36: 'M2', 42: 'M3', 46: 'M4', 81: 'M5'}
CUT, PITCH = 0.26, 0.52
ARRAY_PITCH = 0.62     # 0.36 um spacing in >= 4x4 arrays (V*.2b)
MIM_TOP_PITCH = 0.76   # 0.5 um spacing on a MIM top plate (MIMTM.9)


def um(v):
    return int(round(v*1000))


def via_array(cell, li, vname, b, enc=0.3, pitch=None):
    """Fill box b (dbu Box) with a regular 0.26 um cut array.

    GF180 V*.2b: cut spacing in a 4x4 or larger array >= 0.36 um, so the pitch is 0.62 um unless the array is
    smaller than 4x4 (0.52 um). MIMTM.9 (Via4 on a MIM top plate): pass pitch=0.76 (0.5 um spacing).
    """
    x1, y1, x2, y2 = b.left+um(enc), b.bottom+um(enc), b.right-um(enc), b.top-um(enc)
    def fit(p):
        return (max(0, int((x2-x1-um(CUT))//um(p))+1), max(0, int((y2-y1-um(CUT))//um(p))+1))
    if pitch is None:
        nx, ny = fit(PITCH)
        p = PITCH if (nx < 4 or ny < 4) else ARRAY_PITCH
        if p != PITCH:
            nx, ny = fit(p)
    else:
        p = pitch
        nx, ny = fit(p)
    if nx == 0 or ny == 0:
        return 0
    ox = x1+((x2-x1)-((nx-1)*um(p)+um(CUT)))//2
    oy = y1+((y2-y1)-((ny-1)*um(p)+um(CUT)))//2
    ox, oy = ox//5*5, oy//5*5        # keep cuts on the 5 nm manufacturing grid
    shapes = cell.shapes(li[vname])
    for i in range(nx):
        for j in range(ny):
            x, y = ox+i*um(p), oy+j*um(p)
            shapes.insert(db.Box(x, y, x+um(CUT), y+um(CUT)))
    return nx*ny


def window_regions(layout, cell, window):
    regs = {}
    for name, (l, d) in LAYERS.items():
        idx = layout.find_layer(l, d)
        if idx is None:
            regs[name] = db.Region()
            continue
        it = cell.begin_shapes_rec_touching(idx, window)
        regs[name] = (db.Region(it) & db.Region(window)).merged()
    # Via4 cuts on a MIM top plate (FuseTop 75/0) join the top plate to Metal5, not to the
    # Metal4 bottom plate underneath: they are not Metal4-Metal5 connections.
    ft = layout.find_layer(75, 0)
    if ft is not None:
        top_plate = (db.Region(cell.begin_shapes_rec_touching(ft, window)) & db.Region(window)).merged()
        regs['V4'] = regs['V4'].outside(top_plate)
    return regs


def trace(regs, layer, point, max_iter=40):
    """Metal/via connectivity from a seed point (dbu) on a metal layer."""
    probe = db.Region(db.Box(point.x-5, point.y-5, point.x+5, point.y+5))
    net = {m: db.Region() for m in METALS}
    net[layer] = regs[layer].interacting(probe)
    for _ in range(max_iter):
        before = sum(net[m].count() for m in METALS)
        for a, v, b in CONN:
            vias = regs[v].interacting(net[a]) + regs[v].interacting(net[b])
            if vias.is_empty():
                continue
            net[a] = (net[a] + regs[a].interacting(vias)).merged()
            net[b] = (net[b] + regs[b].interacting(vias)).merged()
        if sum(net[m].count() for m in METALS) == before:
            break
    return net


def touches(net_a, net_b):
    return any(not (net_a[m] & net_b[m]).is_empty() for m in METALS)


def cell_labels(layout, cell, trans, names):
    out = []
    for idx in layout.layer_indexes():
        info = layout.get_info(idx)
        if info.layer not in LABEL_METAL:
            continue
        it = cell.begin_shapes_rec(idx)
        while not it.at_end():
            s = it.shape()
            if s.is_text() and s.text.string in names:
                local = it.trans()*db.Point(s.text.trans.disp.x, s.text.trans.disp.y)
                out.append((s.text.string, LABEL_METAL[info.layer], trans*local))
            it.next()
    return out


def edge_frame(edge):
    """(depth->chip coordinate, along axis) for a custom pad edge."""
    if edge == 'west':
        return (lambda d: 26.0+d), 'y'
    return (lambda d: 3906.0-d), 'y'


def build_bus(ly, top, pdn, li, A, B, width, spacing=1.5, insert=True):
    """Draw >= width-um rail (Metal5) and return (Metal4) buses between pad cells A and B.

    Each bus lands on the ESD_RAIL / VSS metal of both cells, found by connectivity from
    the cells' own labels, and keeps `spacing` from every other shape on its layer.
    """
    out = dict(ok=False, shapes=[])
    ta, tb = A['_trans'], B['_trans']
    ca, cb = ly.cell(A['cell']), ly.cell(B['cell'])
    win = (ta*ca.bbox()) + (tb*cb.bbox())
    win = win.enlarged(um(60), um(60))
    regs = window_regions(ly, top, win)
    labs = {}
    for side, (t, c) in (('A', (ta, ca)), ('B', (tb, cb))):
        for name, layer, p in cell_labels(ly, c, t, ('ESD_RAIL', 'VSS')):
            labs.setdefault((side, name), (layer, p))
    depth_to_chip, _ = edge_frame(A['edge'])
    lo_along = min(win.bottom, win.top)
    along0 = win.bottom+um(60)
    along1 = win.top-um(60)
    for netname, layer in (('ESD_RAIL', 'M5'), ('VSS', 'M4')):
        if ('A', netname) not in labs or ('B', netname) not in labs:
            out[netname] = 'missing label'
            continue
        na = trace(regs, *labs[('A', netname)])
        nb = trace(regs, *labs[('B', netname)])
        other = regs[layer] - na[layer] - nb[layer]
        # Land on each cell's own metal (the nets may already meet through the pad
        # ring and core ring; the bus is the direct low-impedance path between macros).
        own_a = na[layer] & db.Region(ta*ca.bbox())
        own_b = nb[layer] & db.Region(tb*cb.bbox())
        found = None
        for d10 in range(4400, 9600, 50):
            d0 = d10/10.0
            xa, xb = depth_to_chip(d0), depth_to_chip(d0+width)
            band = db.Region(db.Box(um(min(xa, xb)), along0, um(max(xa, xb)), along1))
            pa, pb = own_a & band, own_b & band
            if pa.area() < um(width)*um(5) or pb.area() < um(width)*um(5):
                continue
            ya, yb = pa.bbox().center().y, pb.bbox().center().y
            if abs(ya-yb) < um(100):
                continue
            bus = db.Box(um(min(xa, xb)), min(ya, yb), um(max(xa, xb)), max(ya, yb))
            if (db.Region(bus).sized(um(spacing)) & other).is_empty():
                found = (d0, bus)
                break
        if found is None:
            out[netname] = 'no legal band'
            continue
        d0, bus = found
        if insert:
            pdn.shapes(li[layer]).insert(bus)
        out[netname] = dict(layer=layer, depth_um=d0, width_um=width,
                            rect=[bus.left/1000, bus.bottom/1000, bus.right/1000, bus.top/1000])
        out['shapes'].append(out[netname]['rect'])
    out['ok'] = all(isinstance(out.get(n), dict) for n in ('ESD_RAIL', 'VSS'))
    return out
