#!/usr/bin/env python3
"""Grid connectivity audit of an assembled chip (KLayout python, run in the assembly tool image, read-only on the run dir):
  tool.sh <chip> python3 /repo/scratch/integration/m1-pdn/grid_conn.py > out/<chip>/grid_conn.txt
Physical connectivity of everything above the blocks' device layers that the top level draws (grid pt_pdn, router wiring,
direct landings, island bars, antenna diodes; Metal1-5 + Via1-4) plus every block's own Metal4 / Via4 / Metal5. Each
connected piece that holds grid metal is reported with its supply-pad stubs and the block supply pins (VDD / VSS pins of
nets.json, rectangles from masters.json) it touches. A piece with block pins and no pad stub is a fault; a piece with
neither is floating metal. Also writes /run/../grid_conn_<chip>.json? no: JSON on stdout after the marker line 'JSON'."""
import json, os, sys, collections
import klayout.db as db
sys.path.insert(0, '/asm'); import common as C
R = '/run/'; CH = os.environ.get('CHIP', 'rf')
ly = db.Layout(); ly.read(R+os.environ.get('GC_GDS', 'chip/pt_chip_top.gds')); top = ly.cell('pt_chip_top'); dbu = ly.dbu
um = lambda v: int(round(v/dbu))     # GC_GDS / GC_MAN (run-dir relative): pre-route check on placed.gds (preroute.sh)
LAY = dict(M1=(34, 0), V1=(35, 0), M2=(36, 0), V2=(38, 0), M3=(42, 0), V3=(40, 0), M4=(46, 0), V4=(41, 0), M5=(81, 0))
man = json.load(open(R+os.environ.get('GC_MAN', 'chip/manifest.json'))); MJ = json.load(open(R+'masters.json')); nets = json.load(open(R+'nets.json'))
pads = json.load(open(R+'pads.json')); place = json.load(open(R+'place.json'))
TOPC = {'pt_pdn', 'pt_top_wiring', 'pt_direct_land', 'pt_island_bar', 'pt_antdiode'}
# NEG_LAND=<inst> (negative control, preroute.sh selftest): the pt_direct_land metal over that instance is dropped
_nl = next((b for b in man['instances'] if b['name'] == os.environ.get('NEG_LAND')), None)
NEG_LAND = db.Region(db.Box(*[int(round(v/dbu)) for v in _nl['bbox']]).enlarged(2000, 2000)) if _nl else None
kids = collections.Counter(i.cell.name for i in top.each_inst())
print('top children (non-block):', {k: v for k, v in kids.items() if not any(k == b['cell'] for b in man['instances'])})
blkcells = {b['cell'] for b in man['instances']}
PADCELLS = {b['cell'] for b in man['instances'] if b['name'] in pads.get('pads', {})}
nl = db.Layout(); nl.dbu = dbu; c = nl.create_cell('T'); L = {k: nl.layer(*v) for k, v in LAY.items()}
grid = {'M4': db.Region(), 'M5': db.Region()}
for i in top.each_inst():
    nm = i.cell.name
    if nm == 'pt_top_wiring' and os.environ.get('NOWIRE'): continue
    toplev = nm in TOPC or (nm not in blkcells and not nm.startswith(('gf180mcu', 'sealring', 'retained')))
    # the provider ring (its supply rails) and the custom pad families carry the pad supply pins' path to the supply pads
    # (2026-11-27): all their metal is in the audit, else their DVDD / VSS pins were listed as unfed
    toplev = toplev or nm == 'retained_provider_ring' or nm in PADCELLS
    if not toplev and (nm not in blkcells or os.environ.get('NOBLK')): continue
    iname = next((b['name'] for b in man['instances'] if b['cell'] == nm and db.Trans.from_s(b['trans']) == i.trans), None) if os.environ.get('NEG_BAR') or os.environ.get('NEG_PAD') else None
    if iname and iname in (os.environ.get('NEG_BAR'), os.environ.get('NEG_PAD')): continue      # negative control: this instance's metal left out
    for k in (LAY if toplev else ('M4', 'V4', 'M5')):
        li = ly.find_layer(*LAY[k])
        if li is None: continue
        r = db.Region(i.cell.begin_shapes_rec(li)).transformed(i.trans) if not i.is_regular_array() else db.Region(i.cell.begin_shapes_rec(li)).transformed(i.trans)
        if NEG_LAND is not None and nm == 'pt_direct_land': r -= NEG_LAND     # negative control: one block's direct landing removed
        c.shapes(L[k]).insert(r)
        if nm in ('pt_pdn', 'pt_island_bar') and k in grid: grid[k] += r
for li_k in LAY:          # top cell's own shapes
    li = ly.find_layer(*LAY[li_k])
    if li is not None: c.shapes(L[li_k]).insert(top.shapes(li))
# block supply pins: their rectangles are drawn into the audit layout (the pin metal), probed after extraction
binst = {b['name']: b for b in man['instances']}
PINR = []
inst_, _p, _m = C.load(CH)
SUPN = collections.defaultdict(list)
for n_, i_ in inst_.items():
    for p_, (k_, net_) in i_['pins'].items():
        if net_ in ('VDD', 'VSS'): SUPN[net_].append((n_, p_))
for net in ('VDD', 'VSS'):
    for n, p in SUPN[net]:
        if n not in binst: continue
        b = binst[n]; info = MJ.get(b['master'], {}); o = info.get('origin', [0, 0]); t = db.Trans.from_s(b['trans'])
        for ln, r in info.get('pins', {}).get(p, []):
            k = {'Metal1': 'M1', 'Metal2': 'M2', 'Metal3': 'M3', 'Metal4': 'M4', 'Metal5': 'M5'}[ln]
            PINR.append((k, t*db.Box(um(r[0]+o[0]), um(r[1]+o[1]), um(r[2]+o[0]), um(r[3]+o[1])), n, p, net))
for k, bx, n, p, net in PINR:
    if not os.environ.get('NOPINS') and n not in os.environ.get('EXCL', '').split(','): c.shapes(L[k]).insert(bx)
grid = {k: v.merged() for k, v in grid.items()}
l2n = db.LayoutToNetlist(db.RecursiveShapeIterator(nl, c, []))
Rg = {k: l2n.make_layer(L[k], k) for k in LAY}
for a, v, b in (('M1', 'V1', 'M2'), ('M2', 'V2', 'M3'), ('M3', 'V3', 'M4'), ('M4', 'V4', 'M5')):
    l2n.connect(Rg[a]); l2n.connect(Rg[v]); l2n.connect(Rg[a], Rg[v]); l2n.connect(Rg[v], Rg[b])
l2n.connect(Rg['M5'])
l2n.extract_netlist()
cir = l2n.netlist().circuit_by_name('T')
def probe(layer, box):
    """nets under a rectangle (5 probe points)"""
    out = set()
    for x, y in ((box.center().x, box.center().y), (box.left+1, box.bottom+1), (box.right-1, box.top-1), (box.left+1, box.top-1), (box.right-1, box.bottom+1)):
        n = l2n.probe_net(Rg[layer], db.Point(x, y))
        if n is not None: out.add(n.cluster_id)
    return out
# pad stubs: pdn Metal2 polygons -> net by the nearest supply cell
sup = [(s, 'VDD' if 'dvdd' in v['cell'] else 'VSS', v['bbox']) for s, v in pads['io'].items() if v['cell'].startswith(('gf180mcu_fd_io__dvdd', 'gf180mcu_fd_io__dvss'))]
pm2 = db.Region(ly.cell('pt_pdn').begin_shapes_rec(ly.find_layer(36, 0))).merged()
stub_of = collections.defaultdict(list)
for p in pm2.each():
    b = p.bbox(); cx, cy = b.center().x*dbu, b.center().y*dbu
    s, net, bb = min(sup, key=lambda t: max(t[2][0]-cx, cx-t[2][2], 0)+max(t[2][1]-cy, cy-t[2][3], 0))
    for cid in probe('M2', b): stub_of[cid].append((s, net))
pin_of = collections.defaultdict(list); pa = collections.defaultdict(set)
for k, bx, n, p, net in PINR:
    for cid in probe(k, bx): pa[(n, p, net)].add(cid)
pins_all = [(n, p, net, binst[n]['kind'], binst[n]['master'], sorted(ids)) for (n, p, net), ids in pa.items()]
for n, p, net, *_r, ids in pins_all:
    for cid in ids: pin_of[cid].append((n, p, net))
# pieces holding grid metal
pieces = []
for net in cir.each_net():
    cid = net.cluster_id
    a4 = (l2n.shapes_of_net(net, Rg['M4'], True) & grid['M4']).area()*dbu*dbu/1e6
    a5 = (l2n.shapes_of_net(net, Rg['M5'], True) & grid['M5']).area()*dbu*dbu/1e6
    if a4 + a5 <= 0: continue
    bb = (l2n.shapes_of_net(net, Rg['M4'], True) + l2n.shapes_of_net(net, Rg['M5'], True)).bbox()
    st = stub_of.get(cid, []); pn = pin_of.get(cid, [])
    pieces.append(dict(id=cid, m4_mm2=round(a4, 5), m5_mm2=round(a5, 5), bbox=[round(v*dbu, 1) for v in (bb.left, bb.bottom, bb.right, bb.top)],
                       stub_nets=sorted({n for s, n in st}), n_stubs=len(st), pins=[f'{n}.{p}({nn})' for n, p, nn in pn]))
pieces.sort(key=lambda d: -(d['m4_mm2']+d['m5_mm2']))
fed = {d['id'] for d in pieces if d['n_stubs']}
print('pieces with grid metal:', len(pieces), ' pad-fed:', len(fed))
for d in pieces[:6]: print('  ', {k: (v if k != 'pins' else len(v)) for k, v in d.items()})
# island bars (fp-wired 2026-11-28): a piece holding pt_island_bar Metal5 and no pad stub is its rail net, not VDD / VSS. It
# is fed if it touches the VISL pins of its switches (common.ISLAND_BARS vias); a bar split off its switch is a FAULT
barm5 = db.Region(ly.cell('pt_island_bar').begin_shapes_rec(ly.find_layer(81, 0))).merged() if ly.cell('pt_island_bar') else db.Region()
bar_res = []
for bd in C.ISLAND_BARS.get(CH, []):
    sw = [i_ for i_, p_ in bd.get('vias', []) if p_ == 'VISL' and i_ in binst]
    vis = set()
    for s_ in sw:
        b_ = binst[s_]; info = MJ.get(b_['master'], {}); o = info.get('origin', [0, 0]); t = db.Trans.from_s(b_['trans'])
        for ln, r in info.get('pins', {}).get('VISL', []):
            vis |= probe({'Metal1': 'M1', 'Metal2': 'M2', 'Metal3': 'M3', 'Metal4': 'M4', 'Metal5': 'M5'}[ln], t*db.Box(um(r[0]+o[0]), um(r[1]+o[1]), um(r[2]+o[0]), um(r[3]+o[1])))
    bar_res.append(dict(net=bd['net'], switches=sw, visl_ids=sorted(vis)))
barpiece = {}
for d in pieces:
    if d['n_stubs']: continue
    nt = cir.net_by_cluster_id(d['id'])
    if (l2n.shapes_of_net(nt, Rg['M5'], True) & barm5).is_empty(): continue
    hit = [b for b in bar_res if d['id'] in b['visl_ids']]
    barpiece[d['id']] = hit[0]['net'] if hit else None
print('island bar pieces:', {k: (v or 'NOT FED (no switch VISL)') for k, v in barpiece.items()})
for b in bar_res:
    if not any(v == b['net'] for v in barpiece.values()): print('ISLAND BAR NOT FED:', b['net'], 'switches', b['switches'])
bars_ok = all(v for v in barpiece.values()) and all(any(v == b['net'] for v in barpiece.values()) for b in bar_res)
print('island bars fed through their switches:', bars_ok)
fl = [d for d in pieces if not d['n_stubs'] and d['id'] not in barpiece]
print('floating pieces:', len(fl), 'M4 %.4f mm2, M5 %.4f mm2' % (sum(d['m4_mm2'] for d in fl), sum(d['m5_mm2'] for d in fl)))
print('floating pieces with block supply pins (FAULT):')
for d in fl:
    if d['pins']: print('  ', d)
bad = []
grp = collections.defaultdict(list)
for n, p, net, kind, master, ids in pins_all: grp[(n, net)].append((p, ids))
for (n, net), lst in sorted(grp.items()):
    ok = any(set(ids) & fed for p, ids in lst)
    if not ok: bad.append(dict(inst=n, net=net, master=binst[n]['master'], kind=binst[n]['kind'], pins=[(p, len(ids)) for p, ids in lst]))
# named float exception (coordinator 2026-11-27, pt_wired): pad_tlp VDD / VSS reach neither the ring rails nor the grid; kept
# out of 'unfed' and listed apart (LVS by name / padsup check that nothing else joins them)
FLOATX = {('pad_tlp', 'VDD'), ('pad_tlp', 'VSS')} if CH == 'wired' else set()
floatx = [b for b in bad if (b['inst'], b['net']) in FLOATX]; bad = [b for b in bad if (b['inst'], b['net']) not in FLOATX]
print('named float exceptions (not counted as unfed):', [f"{b['inst']}.{b['net']}" for b in floatx])
# an island bar not fed through its switch counts as an unfed supply (fails signoff's 'every block fed')
if not bars_ok:
    bad += [dict(inst='ISLAND_BAR', net=b['net'], master='pt_island_bar', kind='bar', pins=[]) for b in bar_res if not any(v == b['net'] for v in barpiece.values())]
    bad += [dict(inst='ISLAND_BAR', net='?', master='pt_island_bar', kind='bar piece', pins=[cid]) for cid, v in barpiece.items() if not v]
print('block/net with no pin on a pad-fed piece:', len(bad))
for b in bad: print('  ', b)
# shorts: a pad-fed piece with both VDD and VSS stubs
print('pieces with both VDD and VSS stubs:', [d['id'] for d in pieces if len(d['stub_nets']) > 1])
# drawn coverage per core region (3 x 3, as place.json pdn_regions_pct) counting only grid metal of the pad-fed pieces
fedcid = {d['id']: d['stub_nets'][0] for d in pieces if len(d['stub_nets']) == 1}
core = C.CORE; live = {}
fedshape = {(cid, k): l2n.shapes_of_net(cir.net_by_cluster_id(cid), Rg[k], True) & grid[k] for cid in fedcid for k in ('M4', 'M5')}
for i, cx in enumerate('WCE'):
    for j, ry in enumerate('SMN'):
        x0 = core[0]+(core[2]-core[0])*i/3; x1 = core[0]+(core[2]-core[0])*(i+1)/3; y0 = core[1]+(core[3]-core[1])*j/3; y1 = core[1]+(core[3]-core[1])*(j+1)/3
        bx = db.Region(db.Box(um(x0), um(y0), um(x1), um(y1))); A_ = (x1-x0)*(y1-y0)
        live[ry+cx] = {f'{nt}_{ {"M4": "Metal4", "M5": "Metal5"}[k]}': round(100*(fedshape[(cid, k)] & bx).area()*dbu*dbu/A_, 1) for cid, nt in fedcid.items() for k in ('M4', 'M5')}
print('live coverage per region (pad-fed grid metal, %):', live)
print('drawn coverage per region (place.json, %):', place['pdn_regions_pct'])
print('JSON'); print(json.dumps(dict(pieces=pieces, unfed=bad, pdn_regions_pct=live, island_bars=dict(pieces={str(k): v for k, v in barpiece.items()}, ok=bars_ok), floating_nonbar=len(fl), float_exceptions=[f"{b['inst']}.{b['net']}" for b in floatx])))
if os.environ.get('NOPINS'):     # which pin rectangles touch which pad-fed piece (pin-rectangle bridges and pins left off)
    fedn = {d['id']: d['stub_nets'] for d in pieces if d['n_stubs']}
    shp = {(cid, k): l2n.shapes_of_net(cir.net_by_cluster_id(cid), Rg[k], True).merged() for cid in fedn for k in ('M1', 'M2', 'M3', 'M4', 'M5')}
    for k, bx, n, p, net in PINR:
        hit = sorted({tuple(fedn[cid]) for cid in fedn if not shp[(cid, k)].interacting(db.Region(bx)).is_empty()})
        tag = 'BRIDGE' if len(hit) > 1 else ('WRONG' if hit and net not in hit[0] else ('none' if not hit else 'ok'))
        if tag != 'ok': print('PINCHK', tag, n, p, net, k, [round(v*dbu, 2) for v in (bx.left, bx.bottom, bx.right, bx.top)], hit)
# the digital macro's own supply stripes (masters.json VDD / VSS pins; not conn pins): which piece holds each stripe
if 'digital' in binst:
    b = binst['digital']; info = MJ.get(b['master'], {}); o = info.get('origin', [0, 0]); t = db.Trans.from_s(b['trans'])
    for pn in ('VDD', 'VSS'):
        cnt = collections.Counter()
        for ln, r in info.get('pins', {}).get(pn, []):
            bx = t*db.Box(um(r[0]+o[0]), um(r[1]+o[1]), um(r[2]+o[0]), um(r[3]+o[1]))
            ids = probe({'Metal4': 'M4', 'Metal5': 'M5'}[ln], bx)
            cnt[tuple(sorted(next((tuple(d['stub_nets']) or ('float',) for d in pieces if d['id'] == i), ('nogrid',)) for i in ids))] += 1
        print('MACRO', pn, 'stripes:', sum(cnt.values()), dict(cnt))
    v4 = db.Region(ly.cell('pt_pdn').begin_shapes_rec(ly.find_layer(41, 0))) & db.Region(t*db.Box(um(o[0]), um(o[1]), um(o[0]+float(info['w'])), um(o[1]+float(info['h']))))
    print('MACRO grid Via4 cuts over the macro outline:', v4.count())
if 'digital' in binst and os.environ.get('MACRONET'):
    for pn in ('VDD', 'VSS'):
        ln, r = info['pins'][pn][0]; bx = t*db.Box(um(r[0]+o[0]), um(r[1]+o[1]), um(r[2]+o[0]), um(r[3]+o[1]))
        for i in probe('M4', bx):
            nt = cir.net_by_cluster_id(i)
            for k in ('M1', 'M2', 'M3', 'M4', 'M5'):
                sh = l2n.shapes_of_net(nt, Rg[k], True)
                if not sh.is_empty(): print('MACRONET', pn, i, k, 'area um2 %.0f' % (sh.area()*dbu*dbu), 'bbox', sh.bbox().to_dtype(dbu))
            out_ = (l2n.shapes_of_net(nt, Rg['M5'], True) + l2n.shapes_of_net(nt, Rg['M4'], True)) - db.Region(t*db.Box(um(o[0]), um(o[1]), um(o[0]+float(info['w'])), um(o[1]+float(info['h']))))
            print('MACRONET', pn, 'metal outside the macro outline um2 %.1f' % (out_.area()*dbu*dbu))
