# Stage `abstract` (tool image, KLayout python):  tool.sh <chip> python3 /asm/kl_abstract.py
# 1. Ring: template provider ring + seal ring + ID cells; the chip's custom pad families placed with their bond openings
#    exactly on the template's golden-mask openings; a provider supply cell (dvdd / dvss) at every signal site that the
#    bond map bonds to VDD / VSS (D-SPLIT-SUPSITE, PC-35 drop-in). -> /run/ring.gds, /run/pads.json (real footprints, pins)
# 2. Every master of the chip conn that has a GDS (and the provider IO cells at signal sites) -> /run/lef/<master>.lef
#    abstract from the GDS: outline, pins from the top-cell labels (metal under the label), OBS (see obs()) ; /run/masters.json
import json, os, re, sys, collections
import klayout.db as db
sys.path.insert(0, '/asm')
import common as C

CHIP = os.environ['CHIP']; R = '/repo/'
um = lambda v: int(round(v*1000))
inst, ports, masters = C.load(CHIP)
os.makedirs('/run/lef', exist_ok=True)
LAY = {n: d for n, d, l, v in C.METALS}; LAB = {l: n for n, d, l, v in C.METALS}
# ------------------------------------------------------------------------------------------------ ring and pads
ly = db.Layout(); ly.dbu = 0.001; ly.read(R+C.BASE_RING)
top = ly.cell('custom_assembly_candidate'); top.name = 'pt_chip_top'
for li in ly.layer_indexes(): top.shapes(li).clear()
for i in list(top.each_inst()):
    if i.cell.name.startswith(('custom_', 'attached_tx_')): i.delete()
for c in [c for c in ly.top_cells() if c.name != 'pt_chip_top']: ly.prune_cell(c.cell_index(), -1)
ring = ly.cell('retained_provider_ring')
byname = {ly.cell(i).name.split('$')[0]: ly.cell(i) for i in ring.each_child_cell()}
rail = next(c for n, c in byname.items() if n.startswith('5LM_METAL_RAIL'))
L_PAD = ly.layer(37, 0)
_m = db.Layout(); _m.read(R+C.MASK)
MASK = [q.bbox() for q in db.Region(_m.top_cell().begin_shapes_rec(_m.layer(37, 0))).merged().each()
        if q.bbox().width() < 100000 and q.bbox().height() < 100000]
SITES = C.sites(); BOND = C.bond(CHIP)
site_inst = {}
for i in ring.each_inst():
    b = i.bbox()
    for s, v in SITES.items():
        bb = v['bbox_um']
        if abs(b.center().x/1000-(bb[0]+bb[2])/2) < 2 and abs(b.center().y/1000-(bb[1]+bb[3])/2) < 2 and not i.cell.name.startswith(('gf180mcu_fd_io__fill', '5LM')):
            site_inst[s] = i
man = dict(chip=CHIP, notes=[], supply_swaps=[], ring_sites_replaced=[], pads={}, io={})
imported = {}
def import_cell(key, path, cell):
    if key in imported: return imported[key]
    src = db.Layout(); src.read(path)
    c = src.cell(cell) if cell else None
    if c is None: c = sorted(src.top_cells(), key=lambda t: -t.bbox().area())[0]
    t = ly.create_cell(key); t.copy_tree(c); imported[key] = t
    return t

def footprint(c, tr):
    """real footprint of a placed cell: all drawn layers, 8 um closing, as a few rectangles (largest first)"""
    r = db.Region()
    for li in ly.layer_indexes():
        info = ly.get_info(li)
        if info.datatype in (10, 63) or (info.layer, info.datatype) in ((63, 63), (0, 0)): continue
        r += db.Region(c.begin_shapes_rec(li))
    r = r.merged().sized(um(4)).merged().sized(-um(4)).transformed(tr)
    rects = []
    for p in r.sized(um(2)).merged().each():
        for t in p.decompose_trapezoids(1): rects.append(t.bbox())
    big = db.Region(rects).merged()
    out = sorted(([b.left/1000, b.bottom/1000, b.right/1000, b.top/1000] for b in [q.bbox() for q in big.each()]), key=lambda q: -(q[2]-q[0])*(q[3]-q[1]))
    return out, r

pad_master = {}
for site, side, net, n in BOND:
    if n in inst and inst[n]['master'].startswith('pad_') and inst[n]['master'] not in ('pad_strap',):
        pad_master.setdefault(n, (inst[n]['master'], side, []))[2].append(site)
for n in [n for n, i in inst.items() if i['master'] == 'pad_tlp' and n not in pad_master]:
    man['notes'].append(f'{n} (pad_tlp) has no bond site in bond_map.txt: placed as a core block')
for n, (m, side, ss) in sorted(pad_master.items()):
    cand = C.gds_candidates(masters, m)
    if not cand: man['notes'].append(f'{n}: no GDS for {m}'); continue
    c = import_cell(m, R+cand[0]['gds'], cand[0]['cell']); b = c.bbox()
    tr0 = db.Trans(db.Trans.M45, db.Vector(0, 0)) if side == 'west' else db.Trans(db.Trans.R90, db.Vector(0, 0))
    op = sorted([q.bbox() for q in db.Region(c.begin_shapes_rec(L_PAD)).merged().transformed(tr0).each()], key=lambda q: q.center().y)
    tgt = sorted([db.Box(*[um(v) for v in SITES[s]['bond_opening_bbox_um']]) for s in ss], key=lambda q: q.center().y)
    if len(op) != len(tgt):
        man['notes'].append(f'{n}: {len(op)} bond openings in the cell vs {len(tgt)} sites');
    d = tgt[0].center()-op[0].center()
    tr = db.Trans(d)*tr0
    got = sorted([q.bbox() for q in db.Region(c.begin_shapes_rec(L_PAD)).merged().transformed(tr).each()], key=lambda q: q.center().y)
    err = max(abs(g.left-t.left)+abs(g.bottom-t.bottom)+abs(g.right-t.right)+abs(g.top-t.top) for g, t in zip(got, tgt))/1000
    top.insert(db.CellInstArray(c.cell_index(), tr))
    fp, _ = footprint(c, tr)
    man['pads'][n] = dict(master=m, side=side, sites=ss, trans=str(tr), gds=cand[0]['gds'], sha=cand[0]['sha256'],
                          bbox=[(tr*b).left/1000, (tr*b).bottom/1000, (tr*b).right/1000, (tr*b).top/1000], footprint=fp, opening_error_um=err)
    opening = db.Region(c.begin_shapes_rec(L_PAD)).transformed(tr)
    for i in list(ring.each_inst()):
        nm = i.cell.name
        if 'fill' in nm or nm.startswith('5LM') or '__cor' in nm: continue
        if not (opening & db.Region(i.bbox())).is_empty():
            t = i.trans; i.delete(); ring.insert(db.CellInstArray(rail.cell_index(), t))
            man['ring_sites_replaced'].append(dict(pad=n, was=nm))
# rail-only sites of the base ring that no family covers get a provider analog cell back (template has an opening there)
allop = db.Region(top.begin_shapes_rec(L_PAD)).merged()
asig = byname['gf180mcu_fd_io__asig_5p0']; man['ring_sites_restored'] = []
for i in list(ring.each_inst()):
    ib = i.bbox()
    site = db.Box(26000 if ib.left < 500000 else ib.left, 26000 if ib.bottom < 500000 else ib.bottom,
                  3906000 if ib.right > 3432000 else ib.right, 5096000 if ib.top > 4622000 else ib.top)
    if i.cell.name.startswith('5LM') and (allop & db.Region(site)).is_empty():
        t = i.trans; i.delete(); ring.insert(db.CellInstArray(asig.cell_index(), t))
        man['ring_sites_restored'].append([ib.left/1000, ib.bottom/1000])
# supply bonds on signal sites: provider supply cell at the site (same outline, opening and rails as every ring cell)
dvdd = byname['gf180mcu_fd_io__dvdd']; dvss = byname['gf180mcu_fd_io__dvss']
site_inst = {}
for i in ring.each_inst():
    if i.cell.name.startswith(('gf180mcu_fd_io__fill', '5LM')) or '__cor' in i.cell.name: continue
    b = i.bbox()
    for s, v in SITES.items():
        bb = v['bbox_um']
        if abs(b.center().x/1000-(bb[0]+bb[2])/2) < 3 and abs(b.center().y/1000-(bb[1]+bb[3])/2) < 3: site_inst[s] = i
for site, side, net, n in BOND:
    if n.startswith(('pad_xvdd', 'pad_xvss')) and site in site_inst:
        i = site_inst[site]; was = i.cell.name; t = i.trans
        i.delete(); new = ring.insert(db.CellInstArray((dvdd if net == 'VDD' else dvss).cell_index(), t))
        site_inst[site] = new; man['supply_swaps'].append(dict(site=site, net=net, was=was, now=new.cell.name))
# provider IO cells: site -> cell, transformation (pins come from their abstracts)
for s, i in site_inst.items():
    man['io'][s] = dict(cell=i.cell.name.split('$')[0], trans=str(i.trans), bbox=[i.bbox().left/1000, i.bbox().bottom/1000, i.bbox().right/1000, i.bbox().top/1000])
# pad overlap check (fails the stage): a custom pad's drawn outline may not reach another custom pad, nor the provider IO
# cell of a site that is not one of its own (that cell's metal would join the pad's)
pad_reg = {}
for n, v in man['pads'].items():
    c = ly.cell(v['master']); t = db.Trans.from_s(v['trans']); r = db.Region()
    for li in ly.layer_indexes():
        inf = ly.get_info(li)
        if inf.datatype == 0 and inf.layer in (22, 30, 34, 36, 42, 46, 81, 35, 38, 40, 41, 33): r += db.Region(c.begin_shapes_rec(li))
    pad_reg[n] = r.merged().transformed(t)
man['pad_overlaps'] = []
names = sorted(pad_reg)
for i, a_ in enumerate(names):
    for b_ in names[i+1:]:
        x = pad_reg[a_] & pad_reg[b_]
        if not x.is_empty(): man['pad_overlaps'].append(dict(a=a_, b=b_, with_='custom pad', bbox=str(x.bbox())))
    own = set(man['pads'][a_]['sites'])
    for s, iv in site_inst.items():
        if s in own: continue
        x = pad_reg[a_] & db.Region(iv.bbox())
        if not x.is_empty():
            hit = db.Region(iv.cell.begin_shapes_rec(ly.find_layer(46, 0))).transformed(iv.trans) & pad_reg[a_]
            man['pad_overlaps'].append(dict(a=a_, b=s, with_=iv.cell.name.split('$')[0], bbox=str(x.bbox()), metal4_touch=not hit.is_empty()))
for o in man['pad_overlaps']: print('PAD OVERLAP', o)
allop = db.Region(top.begin_shapes_rec(L_PAD)).merged(); mreg = db.Region(MASK)
man['pad_mask'] = dict(template=len(MASK), not_open=[str(q.bbox()) for q in (mreg-allop).merged().each()], extra=[str(q.bbox()) for q in (allop-mreg).merged().each() if q.bbox().width() < 100000])
ly.write('/run/ring.gds')

# ------------------------------------------------------------------------------------------------ abstracts
def obs(c, pins, full_all):
    """LEF obstruction per metal: the outline on Metal1-3 (and on Metal4/5 too for no-route-over masters), the drawn metal
    (2 um grid, conservative) on Metal4/5 otherwise; a 2 um window around every pin is opened from the pin layer up, and
    inside it the drawn metal is the obstruction. Pins themselves are not obstructed."""
    b = c.bbox(); full = db.Region(b); out = {}
    win = collections.defaultdict(db.Region)
    order = [n for n, *_ in C.METALS]
    for pn, shapes in pins.items():
        for ln, box in shapes:
            for up in order[order.index(ln):]: win[up].insert(box.enlarged(um(2), um(2)))
    for ln, d, l, v in C.METALS:
        li = ly2.find_layer(*d)
        metal = db.Region(c.begin_shapes_rec(li)).merged() if li is not None else db.Region()
        # Metal4/5 of an over-routable block: its drawn metal grown by 1 um (conservative, fewer rectangles)
        base = full if (ln in ('Metal1', 'Metal2', 'Metal3') or full_all) else (metal.sized(um(1)) & full).merged()
        w = win[ln].merged() & full
        o = (base - w) + (metal & w)
        o -= db.Region([bx for pn, sh in pins.items() for l2, bx in sh if l2 == ln])
        out[ln] = o.merged()
    return out

def lef_rects(reg, origin):
    rs = []
    for p in reg.each():
        for t in p.decompose_trapezoids(1):
            bb = t.bbox()
            if bb.width() > 0 and bb.height() > 0: rs.append(bb.moved(-origin))
    return rs

def abstract(key, path, cellname, full_all, kind, want_pins):
    global ly2
    ly2 = db.Layout(); ly2.read(path)
    c = ly2.cell(cellname) if cellname else None
    if c is None: c = sorted(ly2.top_cells(), key=lambda t: -t.bbox().area())[0]
    b = c.bbox(); org = b.p1
    pins = collections.defaultdict(list)
    for ln, d, l, v in C.METALS:
        for lab_l in (l,):
            li = ly2.find_layer(*lab_l)
            if li is None: continue
            dl = ly2.find_layer(*d)
            for s in c.shapes(li).each():
                if not s.is_text(): continue
                name = s.text.string; pt = s.text.trans.disp
                if dl is None: continue
                around = db.Box(pt.x-um(25), pt.y-um(25), pt.x+um(25), pt.y+um(25))
                reg = db.Region(c.begin_shapes_rec_touching(dl, db.Box(pt, pt).enlarged(1, 1))).merged()
                hit = [p for p in reg.each() if p.inside(pt)]      # not bbox: a ring-shaped other-net polygon round the label became the pin (VDD/VSS joins, 2026-11-24)
                if not hit: continue
                for p in hit:
                    rr = db.Region(p) & db.Region(around)
                    for q in rr.each():
                        for t in q.decompose_trapezoids(1):
                            if t.bbox().width() >= 200 and t.bbox().height() >= 200: pins[name].append((ln, t.bbox()))
    # PIN_UP masters (common): a pin labelled only on Metal1 deep in the cell also gets the cell's own Metal4/5 of the same
    # net (traced through Via1-4 from the label), so the router lands from above instead of dropping a Via1 stack next to
    # other-net metal (por: VDD hook shorted to its internal Metal2, VDD/VSS join, 2026-11-24)
    if key in C.PIN_UP:
        l2n = db.LayoutToNetlist(db.RecursiveShapeIterator(ly2, c, []))
        lay = {}
        for ln, d, l, v in C.METALS:
            li = ly2.find_layer(*d); lay[ln] = l2n.make_layer(li, ln) if li is not None else l2n.make_layer(ln)
            if v:
                vi = ly2.find_layer(*v); lay['V'+ln] = l2n.make_layer(vi, 'V'+ln) if vi is not None else l2n.make_layer('V'+ln)
        prev = None
        for ln, d, l, v in C.METALS:
            l2n.connect(lay[ln])
            if v: l2n.connect(lay['V'+ln]); l2n.connect(lay[prev], lay['V'+ln]); l2n.connect(lay['V'+ln], lay[ln])
            prev = ln
        l2n.extract_netlist()
        li1 = ly2.find_layer(*C.METALS[0][2])
        for s in (c.shapes(li1).each() if li1 is not None else []):
            if not s.is_text() or s.text.string not in C.PIN_UP[key]: continue
            net = l2n.probe_net(lay['Metal1'], db.Point(s.text.trans.disp))
            if net is None: continue
            for up in ('Metal4', 'Metal5'):
                reg = l2n.shapes_of_net(net, lay[up], True).merged()
                for p in reg.each():
                    for t in p.decompose_trapezoids(1):
                        if t.bbox().width() >= 1000 and t.bbox().height() >= 1000: pins[s.text.string].append((up, t.bbox()))
            if any(x[0] != 'Metal1' for x in pins[s.text.string]): pins[s.text.string] = [x for x in pins[s.text.string] if x[0] != 'Metal1']
    pins = {k: v[:40] for k, v in pins.items()}
    extra_ = sorted(set(pins)-set(want_pins)) if want_pins else []
    if want_pins: pins = {k: v for k, v in pins.items() if k in want_pins}     # labels that are not conn pins (e.g. adc SEN_A test labels) stay obstruction: a VSS hook was routed into SEN_A, 2026-11-24
    o = obs(c, pins, full_all)
    L = [f'MACRO {key}', '  CLASS BLOCK ;', '  ORIGIN 0 0 ;', f'  FOREIGN {key} 0 0 ;', f'  SIZE {b.width()/1000:.3f} BY {b.height()/1000:.3f} ;', '  SYMMETRY X Y R90 ;']
    pin_out = {}
    for pn, sh in sorted(pins.items()):
        L += [f'  PIN {pn}', '    DIRECTION INOUT ;', '    USE SIGNAL ;', '    PORT']
        for ln, bx in sh:
            q = bx.moved(-db.Vector(org))
            L.append(f'      LAYER {ln} ; RECT {q.left/1000:.3f} {q.bottom/1000:.3f} {q.right/1000:.3f} {q.top/1000:.3f} ;')
        L += ['    END', f'  END {pn}']
        pin_out[pn] = [(ln, [(bx.left-org.x)/1000, (bx.bottom-org.y)/1000, (bx.right-org.x)/1000, (bx.top-org.y)/1000]) for ln, bx in sh]
    L.append('  OBS')
    nobs = 0
    for ln, reg in o.items():
        rs = lef_rects(reg, db.Vector(org))
        if rs: L.append(f'    LAYER {ln} ;')
        for q in rs: L.append(f'      RECT {q.left/1000:.3f} {q.bottom/1000:.3f} {q.right/1000:.3f} {q.top/1000:.3f} ;'); nobs += 1
    L += ['  END', f'END {key}', '']
    open(f'/run/lef/{key}.lef', 'w').write('\n'.join(L))
    missing = [p for p in want_pins if p not in pins] if want_pins else []
    return dict(w=b.width()/1000, h=b.height()/1000, origin=[org.x/1000, org.y/1000], cell=c.name, pins=pin_out, kind=kind,
                full_obs=full_all, obs_rects=nobs, missing_pins=missing, extra_labels=extra_)

MJ = {}
used = sorted({i['master'] for i in inst.values() if not i['master'].startswith(C.PROVIDER)} | {'gf180mcu_fd_io__'+x for x in ('bi_24t', 'in_c', 'asig_5p0')})
for v in C.STAGED.get(CHIP, {}).values(): used.append(v['master'])
for m in used:
    if m.startswith('gf180mcu_fd_io__'):
        cand = [dict(gds=C.BASE_RING, cell=None, kind='provider', sha256='')]
        tmp = db.Layout(); tmp.read(R+C.BASE_RING)
        nm = next(tmp.cell(i).name for i in tmp.each_cell_top_down() if tmp.cell(i).name.split('$')[0] == m)
        cand[0]['cell'] = nm
    elif any(v['master'] == m for v in C.STAGED.get(CHIP, {}).values()):
        v = next(v for v in C.STAGED[CHIP].values() if v['master'] == m)
        cand = [dict(gds=v['gds'], cell=v['cell'], kind='staged', sha256='')]
    else:
        cand = C.gds_candidates(masters, m, CHIP)
    if not cand:
        MJ[m] = dict(kind='none'); continue
    src = cand[0]
    try:
        info = abstract(m, R+src['gds'], src['cell'], m in C.NO_OVER or m.startswith(('pad_', 'gf180mcu_fd_io')), src['kind'], C.master_pins(masters, m))
    except Exception as e:
        MJ[m] = dict(kind='error', error=str(e)[:300]); continue
    info.update(gds=src['gds'], sha=src['sha256'])
    lefp = C.CHIP_LEF.get((CHIP, m))
    if lefp and os.path.exists(R+lefp):          # owner's LEF: pins (and obstructions) as the owner abstracted them
        txt = open(R+lefp).read(); pins = {}
        for pm in re.finditer(r'\n\s*PIN (\S+)(.*?)\n\s*END \1', txt, re.S):
            cur = None
            for ln_ in pm.group(2).split('\n'):
                t_ = ln_.split()
                if t_[:1] == ['LAYER']: cur = t_[1]
                elif t_[:1] == ['RECT'] and cur: pins.setdefault(pm.group(1), []).append((cur, [float(v) for v in t_[1:5]]))
        info['pins'] = pins; info['origin'] = [0.0, 0.0]; info['lef'] = lefp
        mm = re.search(r'MACRO (\S+)', txt).group(1)
        open(f'/run/lef/{m}.lef', 'w').write(txt.replace(f'MACRO {mm}', f'MACRO {m}').replace(f'END {mm}', f'END {m}'))
    MJ[m] = info
    print(f"{m:28s} {info['w']:8.1f} x {info['h']:7.1f}  pins {len(info['pins']):3d}  missing {len(info['missing_pins']):3d}  obs {info['obs_rects']}", flush=True)
json.dump(MJ, open('/run/masters.json', 'w'), indent=0)
json.dump(man, open('/run/pads.json', 'w'), indent=0)
print('pads:', {n: (v['master'], round(v['opening_error_um'], 3)) for n, v in man['pads'].items()}, '| mask', man['pad_mask'], '| swaps', len(man['supply_swaps']), '| PAD OVERLAPS', len(man['pad_overlaps']))
if man['pad_overlaps']: sys.exit(3)
for n in man['notes']: print(' note:', n)
