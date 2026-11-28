"""Pre-route in-context DRC windows (KLayout python; preroute.sh runs it). Two modes:

  build:  klayout -b -zz -r preroute_win.py -rd mode=build -rd inp=<placed.gds> -rd out=<windows.gds> -rd win=<windows.json>
          [-rd margin=15] [-rd only=<inst,inst>] [-rd neg=<case>]
  attr:   klayout -b -zz -r preroute_win.py -rd mode=attr -rd inp=<placed.gds> -rd win=<windows.json> -rd rdb=<report.lyrdb>
          -rd res=<result.json>

build: one window per block / custom-pad instance of the placed (pre-route) chip: the instance bbox + margin, holding
everything placed there before routing (the block, provider ring, pt_pdn grid, island bars RAIL_*, plates, direct
landings, pads, neighbours). Only the BEOL layers the deck's metal / via / MetalTop / slot rules read are kept
(Metal2-5, Via2-4, Via5, MetalTop, Pad): FEOL, Metal1 and Via1 are signed by each block owner and cost most of the run.
Each window is clipped (hierarchy kept) and placed on its own tile of the output layout, so windows never touch.
neg=<case> draws one known fault into the windows for the negative tests (see preroute.sh selftest).

attr: maps every deck marker back to chip coordinates and its window; markers within EDGE of a window's clip edge are
clip artefacts and dropped (the margin keeps the instance bbox EDGE+ inside). Each remaining marker is classed by the
top-level instances whose shapes touch it: 'context' (a top-level layer cell or a second instance involved; the classes
that cost full routes) or 'internal' (only the block itself: block-owner DRC, reported, not gated). Duplicates from
overlapping windows are merged by chip location."""
import pya, json, re, gzip, collections, time
T0 = time.time()
KEEP = {(36, 0), (38, 0), (42, 0), (40, 0), (46, 0), (41, 0), (81, 0), (82, 0), (53, 0), (37, 0)}
# top-level cells drawn before routing that every window keeps as context (never a window of their own)
CONTEXT = ('retained_provider_ring', 'pt_pdn', 'pt_island_bar', 'pt_direct_land', 'sealring', 'pt_antdiode', 'pt_antdiode_s',
           'pt_plates', 'gf180mcu_ws_ip__')
EDGE = 2.0         # um: markers this close to a clip edge are clip artefacts
TILE = 50.0        # um gap between window tiles
g = globals()
mode = g.get('mode', 'build'); RES_PATH = g.get('res'); margin = float(g.get('margin', 15)); only = [s for s in g.get('only', '').split(',') if s]
ly = pya.Layout(); ly.read(inp); top = ly.top_cell(); dbu = ly.dbu
U = lambda v: int(round(v / dbu))


def is_ctx(name): return name.startswith(CONTEXT)


def windows():
    """[(name, cell, box)] one per top-level non-context instance; names from the GDS (cell name + index)"""
    out = []; seen = collections.Counter()
    for i in top.each_inst():
        cn = i.cell.name
        if is_ctx(cn) or i.cell.bbox().empty(): continue
        if cn.startswith('gf180mcu_fd_io'): continue          # stock IO cells: provider signed with the ring
        seen[cn] += 1; nm = f'{cn}#{seen[cn]}' if seen[cn] > 1 else cn
        out.append((nm, cn, i.bbox()))
    return out


if mode == 'build':
    if g.get('padfix', '0') == '1':       # the pads as the flow now imports them (pad_cup.finalize, kl_abstract)
        import sys; sys.path.insert(0, g.get('asm', '/a')); import pad_cup
        for c in sorted({i.cell for i in top.each_inst() if i.cell.name.startswith('pad_')}, key=lambda c: c.name):     # the pad family cells placed on the chip
            print('padfix', c.name, pad_cup.finalize(ly, c, g.get('padref')))
    for li in list(ly.layer_indexes()):
        info = ly.get_info(li)
        if (info.layer, info.datatype) not in KEEP: ly.delete_layer(li)
    neg = g.get('neg', ''); negbox = None
    W = windows()
    if only: W = [w for w in W if w[0] in only or w[1] in only]
    tc = top.cell_index()
    if neg:      # known faults, drawn into the top cell (chip coordinates) before clipping
        L = lambda a, b: ly.layer(a, b)
        bx = {w[0]: w[2] for w in W}
        tgt = next((b for n, b in bx.items() if n.startswith(g.get('negblk', 'pt_wiredtx8'))), W[0][2])
        c = tgt.center()
        if neg == 'v4_overlap':        # a Via4 cut overlapping another off-lattice: V4.1 / V4.2a
            top.shapes(L(41, 0)).insert(pya.Box(c.x, c.y, c.x + U(0.26), c.y + U(0.26)))
            top.shapes(L(41, 0)).insert(pya.Box(c.x + U(0.13), c.y + U(0.1), c.x + U(0.39), c.y + U(0.36)))
            top.shapes(L(46, 0)).insert(pya.Box(c.x - U(1), c.y - U(1), c.x + U(1.4), c.y + U(1.4)))
            top.shapes(L(81, 0)).insert(pya.Box(c.x - U(1), c.y - U(1), c.x + U(1.4), c.y + U(1.4)))
        elif neg == 'm5_space':        # two Metal5 bars 0.2 um apart: Metal5 / top-metal spacing
            top.shapes(L(81, 0)).insert(pya.Box(c.x, c.y, c.x + U(10), c.y + U(2)))
            top.shapes(L(81, 0)).insert(pya.Box(c.x, c.y + U(2.2), c.x + U(10), c.y + U(4.2)))
        elif neg == 'v3_overlap':
            top.shapes(L(40, 0)).insert(pya.Box(c.x, c.y, c.x + U(0.26), c.y + U(0.26)))
            top.shapes(L(40, 0)).insert(pya.Box(c.x + U(0.1), c.y + U(0.13), c.x + U(0.36), c.y + U(0.39)))
            top.shapes(L(42, 0)).insert(pya.Box(c.x - U(1), c.y - U(1), c.x + U(1.4), c.y + U(1.4)))
            top.shapes(L(46, 0)).insert(pya.Box(c.x - U(1), c.y - U(1), c.x + U(1.4), c.y + U(1.4)))
        else: raise SystemExit(f'unknown neg {neg}')
        negbox = [round(v * dbu, 3) for v in (c.x - U(1), c.y - U(1), c.x + U(10), c.y + U(4.2))]
    boxes = [b.enlarged(U(margin), U(margin)) & top.bbox() for _, _, b in W]
    clips = ly.multi_clip(tc, boxes)
    wt = ly.create_cell('PREROUTE_WINDOWS'); rows = []; x = 0; y = 0; rowh = 0; ROWW = U(20000)
    for (nm, cn, b), bb, ci in zip(W, boxes, clips):
        if x + bb.width() > ROWW and x: x = 0; y += rowh + U(TILE); rowh = 0
        d = pya.Vector(x - bb.left, y - bb.bottom)
        wt.insert(pya.CellInstArray(ci, pya.Trans(d)))
        rows.append(dict(name=nm, cell=cn, bbox=[round(v * dbu, 3) for v in (b.left, b.bottom, b.right, b.top)],
                         win=[round(v * dbu, 3) for v in (bb.left, bb.bottom, bb.right, bb.top)], shift=[d.x * dbu, d.y * dbu]))
        x += bb.width() + U(TILE); rowh = max(rowh, bb.height())
    opt = pya.SaveLayoutOptions(); opt.add_cell(wt.cell_index())
    ly.write(out, opt)
    json.dump(dict(inp=inp, margin=margin, edge=EDGE, neg=neg, negbox=negbox, windows=rows), open(win, 'w'), indent=0)
    print(f'{len(rows)} windows, area {sum((r["win"][2]-r["win"][0])*(r["win"][3]-r["win"][1]) for r in rows)/1e6:.2f} mm2, build {time.time()-T0:.1f} s')

else:
    wj = json.load(open(win)); WR = wj['windows']
    for r in WR: r['tile'] = pya.DBox(r['win'][0] + r['shift'][0], r['win'][1] + r['shift'][1], r['win'][2] + r['shift'][0], r['win'][3] + r['shift'][1])
    # instance shape probes on the stripped BEOL layers
    lis = [li for li in ly.layer_indexes() if (ly.get_info(li).layer, ly.get_info(li).datatype) in KEEP]
    insts = [(i, i.cell.name, i.dbbox()) for i in top.each_inst()]
    RL = {'V2': [(38, 0), (36, 0), (42, 0)], 'V3': [(40, 0), (42, 0), (46, 0)], 'V4': [(41, 0), (46, 0), (81, 0)], 'V5': [(82, 0), (81, 0), (53, 0)],
          'M2': [(36, 0)], 'M3': [(42, 0)], 'M4': [(46, 0)], 'M5': [(81, 0)], 'MT': [(81, 0), (53, 0)], 'MSLOT5': [(81, 0)]}
    def rule_layers(rule):
        k = next((k for k in sorted(RL, key=len, reverse=True) if rule.upper().startswith(k)), None)
        out = [ly.find_layer(*l) for l in RL[k]] if k else lis
        return [li for li in out if li is not None]
    def owners(db_box, rule=''):
        b = pya.Box(U(db_box.left) - 1, U(db_box.bottom) - 1, U(db_box.right) + 1, U(db_box.top) + 1); out = set()
        for i, cn, ib in insts:
            if not ib.overlaps(db_box.enlarged(0.002, 0.002)): continue
            ti = i.dcplx_trans.inverted(); lb = ti * pya.DBox(b.left * dbu, b.bottom * dbu, b.right * dbu, b.top * dbu)
            lbi = pya.Box(U(lb.left), U(lb.bottom), U(lb.right), U(lb.top))
            if any(not i.cell.begin_shapes_rec_touching(li, lbi).at_end() for li in rule_layers(rule)): out.add(cn)
        if NEG and NEG.overlaps(db_box): out.add('<drawn fault>')
        return out
    NEG = pya.DBox(*wj['negbox']) if wj.get('negbox') else None
    op = gzip.open if rdb.endswith('.gz') else open
    txt = op(rdb, 'rt').read()
    items = re.findall(r'<item>(.*?)</item>', txt, re.S)
    # deep-mode markers are reported in the coordinates of the cell they occur in: map them through every placement of
    # that cell in the window layout to the window tiles, then back to chip coordinates
    wl = pya.Layout(); wl.read(wgds); wt = wl.cell('PREROUTE_WINDOWS'); PL = {}
    def placements(cn):
        if cn in PL: return PL[cn]
        c = wl.cell(cn); out = []
        if c is None: PL[cn] = out; return out
        if c.cell_index() == wt.cell_index(): out = [pya.DCplxTrans()]
        else:
            ri = pya.RecursiveInstanceIterator(wl, wt); ri.targets = [c.cell_index()]
            while not ri.at_end():
                if ri.inst_cell().cell_index() == c.cell_index(): _t = ri.current_inst_element().specific_cplx_trans(); _c = pya.CplxTrans(wl.dbu); out.append(ri.dtrans() * (_c * _t * _c.inverted()))
                ri.next()
        PL[cn] = out; return out
    seen = {}; dropped = 0
    for it in items:
        cat = re.search(r'<category>(.*?)</category>', it, re.S).group(1).strip().strip("'").split(':')[0].strip("' ")
        vals = re.findall(r'(-?\d+\.?\d*),(-?\d+\.?\d*)', ' '.join(re.findall(r'<value>(.*?)</value>', it, re.S)))
        if not vals: continue
        xs = [float(a) for a, _ in vals]; ys = [float(b) for _, b in vals]
        mb0 = pya.DBox(min(xs), min(ys), max(xs), max(ys))
        cm = re.search(r'<cell>(.*?)</cell>', it, re.S); cn = cm.group(1).strip() if cm else 'PREROUTE_WINDOWS'
        for tr in placements(cn):
          mb = tr * mb0
          r = next((r for r in WR if r['tile'].contains(mb.center())), None)
          if r is None: continue
          t = r['tile']
          if min(mb.left - t.left, t.right - mb.right, mb.bottom - t.bottom, t.top - mb.top) < EDGE: dropped += 1; continue
          cb = mb.moved(pya.DVector(-r['shift'][0], -r['shift'][1]))
          key = (cat, round(cb.left, 2), round(cb.bottom, 2), round(cb.right, 2), round(cb.top, 2))
          if key in seen: seen[key]['windows'].add(r['name']); continue
          seen[key] = dict(rule=cat, box=[round(v, 3) for v in (cb.left, cb.bottom, cb.right, cb.top)], windows={r['name']})
    for m in seen.values():
        ow = owners(pya.DBox(*m['box']), m['rule']); m['owners'] = sorted(ow)
        m['cls'] = 'context' if (len(ow) != 1 or any(is_ctx(o) or o.startswith('<') for o in ow)) else 'internal'
        m['windows'] = sorted(m['windows'])
    per = collections.defaultdict(lambda: collections.Counter())
    pair = collections.Counter()
    for m in seen.values():
        for w in m['windows']: per[w][(m['cls'], m['rule'])] += 1
        pair[(m['cls'], m['rule'], ' + '.join(m['owners']))] += 1
    ctx = sum(1 for m in seen.values() if m['cls'] == 'context')
    res = dict(markers=len(seen), context=ctx, internal=len(seen) - ctx, edge_dropped=dropped,
               by_class=[dict(cls=c, rule=r, owners=o, n=n) for (c, r, o), n in pair.most_common()],
               per_window={w: {f'{c}:{r}': n for (c, r), n in sorted(v.items())} for w, v in sorted(per.items())},
               examples=[m for m in seen.values() if m['cls'] == 'context'][:40])
    json.dump(res, open(RES_PATH, 'w'), indent=1)
    print(f'markers {len(seen)}: context {ctx}, internal {len(seen) - ctx} (clip-edge dropped {dropped}); attr {time.time()-T0:.1f} s')
    for (c, r, o), n in pair.most_common(25): print(f'  {n:6d} {c:8s} {r:10s} {o}')
