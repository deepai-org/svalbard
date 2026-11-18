# Die-fit ledger: measure every block layout on disk (read-only). Runs in the pinned analog image (KLayout python),
# one process, one thread:  see run_measure.sh.  Output /work/measured.json (one record per target).
# Per layout: top cell, bbox, and inside the bbox
#   empty20   = area with NOTHING drawn (any physical layer, 3 um keep-off) in pieces >= 20 um wide  (dead whitespace)
#   nodev20   = area with no device layer (COMP, Poly2, Nwell, MIM, 3 um keep-off) >= 20 um wide       (channels + whitespace)
#   m45free20 = Metal4/Metal5/MIM-free area >= 20 um wide (grid plates, through-routing)
#   m3free20  = Metal3-free area >= 20 um wide (through-routing of static control)
#   comp/mim/ind = merged COMP, MIM top plate, inductor marker area; rects = largest empty rectangles (w, h, x, y)
import klayout.db as db, json, sys, time
R = '/repo/'; P = R + 'projects/programmable_transceiver_platform/analog/'; S = R + 'scratch/'
T = json.load(open('/work/targets.json'))
PHYS = [(12,0),(21,0),(204,0),(22,0),(30,0),(33,0),(34,0),(35,0),(36,0),(38,0),(42,0),(40,0),(46,0),(41,0),(81,0),(75,0),(53,0)]
DEV = [(21,0),(22,0),(30,0),(75,0)]
def reg(ly, t, lts):
    r = db.Region()
    for lt in lts:
        i = ly.find_layer(*lt)
        if i is not None: r += db.Region(t.begin_shapes_rec(i))
    return r.merged()
def open20(r, dbu): k = int(10/dbu); return r.sized(-k).sized(k) & r
out = {}
try: out = json.load(open('/work/measured.json'))
except Exception: pass
only = sys.argv[1:]
for name, spec in T.items():
    if only and name not in only: continue
    if name in out and 'error' not in out[name] and not only: continue
    f = spec['gds'].replace('P/', P).replace('S/', S); t0 = time.time()
    try:
        ly = db.Layout(); ly.read(f); dbu = ly.dbu
        if spec.get('top'): t = ly.cell(spec['top'])
        else: t = max(ly.top_cells(), key=lambda c: c.bbox().area())
        bx = t.bbox(); B = db.Region(bx); k3 = int(3/dbu); a = lambda r: round(r.area()*dbu*dbu, 1)
        occ = reg(ly, t, PHYS); pb = occ.bbox()
        rec = dict(file=spec['gds'], top=t.name, w=round(bx.width()*dbu, 2), h=round(bx.height()*dbu, 2), bbox_um2=round(bx.area()*dbu*dbu, 1),
                   phys_w=round(pb.width()*dbu, 2), phys_h=round(pb.height()*dbu, 2))
        if not spec.get('light'):
            e = open20(B - occ.sized(k3), dbu); rec['empty20'] = a(e)
            rl = []
            for p in e.each():
                # largest inscribed axis rectangle is expensive; report the polygon bbox only when the polygon is a box
                b = p.bbox()
                if p.is_box(): rl.append([round(b.width()*dbu, 1), round(b.height()*dbu, 1), round((b.left-bx.left)*dbu, 1), round((b.bottom-bx.bottom)*dbu, 1)])
            rec['rects'] = sorted(rl, key=lambda r: -r[0]*r[1])[:4]
            # strips along each bbox edge that are empty for the whole edge length (bbox could shrink): depth in um
            def edge_free(side):
                d = 0; step = int(2/dbu)
                while d < min(bx.width(), bx.height())//2:
                    if side == 'l': s = db.Box(bx.left+d, bx.bottom, bx.left+d+step, bx.top)
                    if side == 'r': s = db.Box(bx.right-d-step, bx.bottom, bx.right-d, bx.top)
                    if side == 'b': s = db.Box(bx.left, bx.bottom+d, bx.right, bx.bottom+d+step)
                    if side == 't': s = db.Box(bx.left, bx.top-d-step, bx.right, bx.top-d)
                    if not (occ & db.Region(s)).is_empty(): break
                    d += step
                return round(d*dbu, 1)
            rec['edge_free'] = {s: edge_free(s) for s in 'lrbt'}
            dev = reg(ly, t, DEV); rec['nodev20'] = a(open20(B - dev.sized(k3), dbu))
            rec['m45free20'] = a(open20(B - reg(ly, t, [(46,0),(81,0),(75,0),(41,0)]).sized(k3), dbu))
            rec['m3free20'] = a(open20(B - reg(ly, t, [(42,0)]).sized(k3), dbu))
            rec['m2free20'] = a(open20(B - reg(ly, t, [(36,0)]).sized(k3), dbu))
            rec['comp'] = a(reg(ly, t, [(22,0)])); rec['nwell'] = a(reg(ly, t, [(21,0)])); rec['mim'] = a(reg(ly, t, [(75,0)]))
            rec['ind'] = a(reg(ly, t, [(151,5)])); rec['m5'] = a(reg(ly, t, [(81,0)])); rec['m4'] = a(reg(ly, t, [(46,0)]))
            rec['res'] = a(reg(ly, t, [(110,5)])); rec['moscap'] = a(reg(ly, t, [(166,5)]))
        if spec.get('bands'):   # pads: occupied lateral extent per 50 um of depth (L-shaped footprints)
            long_y = bx.height() > bx.width(); L = bx.height() if long_y else bx.width(); step = int(50/dbu); pos = 0; bands = []
            while pos < L:
                cb = db.Box(bx.left, bx.bottom+pos, bx.right, min(bx.top, bx.bottom+pos+step)) if long_y else db.Box(bx.left+pos, bx.bottom, min(bx.right, bx.left+pos+step), bx.top)
                r = occ & db.Region(cb); b = r.bbox()
                if r.is_empty(): bands.append([round(pos*dbu), None, None])
                else: bands.append([round(pos*dbu)] + ([round((b.left-bx.left)*dbu, 1), round((b.right-bx.left)*dbu, 1)] if long_y else [round((b.bottom-bx.bottom)*dbu, 1), round((b.top-bx.bottom)*dbu, 1)]))
                pos += step
            rec['bands'] = bands; rec['occ_um2'] = a(occ.sized(k3).sized(-k3))
        rec['sec'] = round(time.time()-t0, 1); out[name] = rec
    except Exception as ex:
        out[name] = dict(file=spec['gds'], error=str(ex))
    print(name, json.dumps(out[name])[:400], flush=True)
    json.dump(out, open('/work/measured.json', 'w'), indent=1)
