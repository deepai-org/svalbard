# KLayout: top-level LVS with black-boxed blocks, on the GDS as it is on disk (nothing is abstracted or stripped).
#   kl.sh lvs/top_lvs.py -rd gds=<rel. to run dir> -rd top=<cell> -rd ref=<spice rel. to run dir> -rd out=<dir rel. to run dir>
#                        [-rd manifest=<json>] [-rd boxes=<comma list of cell-name globs to black-box; default: every direct child of top>]
#                        [-rd strip=<cell-name prefix to remove>] [-rd skip=<instances whose cell is a stand-in>]
#                        [-rd flatten=<globs of direct children of the top cell to flatten first, e.g. the pad ring>]
# Layout side : Metal1..Metal5, Via1..Via4 and the MIM top plate (FuseTop) are extracted hierarchically through ALL cells,
#               including the inside of the black boxes. A black box keeps its pins only. A pin is a block net that the level
#               above touches; its name is the text label on that net in the block's top cell. So a top-level wire that lands
#               on unlabelled block-internal metal shows up as a pin without a name (reported as "internal"), and two block
#               pins joined inside the block show up as one pin with two names. Dummy fill (datatype 4) is not read.
# Compare     : (1) KLayout netlist compare of the black-box netlists (topological; pins of black boxes by name).
#               (2) with a manifest (instance name <-> cell and placement): net by net by name: open / short / internal /
#                   not checkable (other end not bound to a layout cell), which is what one needs to fix a top level.
# Exit status 0 only if (1) matches (and, with a manifest, (2) has no open, short or internal finding).
import fnmatch, json, os, re, sys, time, collections
import klayout.db as db

t0 = time.time()
G = dict(globals())
REF = G['ref']
RUN = '/run/'
outdir = RUN+out; os.makedirs(outdir, exist_ok=True)
ly = db.Layout(); ly.read(RUN+gds)
topc = ly.cell(top)
for pat in filter(None, G.get('flatten', '').split(',')):
    for inst in list(topc.each_inst()):
        if fnmatch.fnmatch(inst.cell.name, pat): inst.flatten(1)
for c in ly.each_cell():       # optional: strip a uniquifying prefix from cell names (routed sub-assemblies)
    if G.get('strip') and c.name.startswith(G['strip']): c.name = c.name[len(G['strip']):]
# template cells carry a '$N' suffix (provider pad cells: gf180mcu_fd_io__bi_24t$1); SPICE reads '$' as a comment, so they
# take their base name where it is free (the reference names provider cells so: chips/provider_io.py, gen_netlist.py)
REN = {}
_kh = G.get('manifest') and any(i.get('kind') == 'provider' for i in json.load(open(RUN+G['manifest']))['instances'])
for c in (list(ly.each_cell()) if _kh else []):      # only when the manifest binds provider cells (KH_CONN runs)
    base = c.name.split('$')[0]
    if base != c.name and ly.cell(base) is None and base not in REN.values(): REN[c.name] = base
for o_, n_ in REN.items(): ly.cell(o_).name = n_
children = sorted({inst.cell.name for inst in topc.each_inst()})
pats = list(filter(None, G.get('boxes', '').split(','))) or ['*']
boxes = [c for c in children if any(fnmatch.fnmatch(c, p) for p in pats)]

# ---------------------------------------------------------------- reference netlist (plain SPICE subset: .subckt / X / .ends)
def read_spice(path):
    lines = []
    for ln in open(path):
        ln = ln.rstrip('\n')
        if ln.startswith('+') and lines: lines[-1] += ' '+ln[1:]
        else: lines.append(ln)
    sub, cur = {}, None
    for ln in lines:
        s = ln.split('$')[0].strip()
        if not s or s[0] == '*': continue
        t = s.split()
        if t[0].lower() == '.subckt': cur = dict(pins=[p for p in t[2:] if '=' not in p], x=[]); sub[t[1]] = cur
        elif t[0].lower() == '.ends': cur = None
        elif t[0][0] in 'xX' and cur is not None:
            pos = [p for p in t[1:] if '=' not in p]
            cur['x'].append((t[0][1:], pos[:-1], pos[-1]))
    return sub
ref = read_spice(RUN+REF)
assert top in ref, f'{top} not in reference netlist'

# ---------------------------------------------------------------- layout extraction
l2n = db.LayoutToNetlist(db.RecursiveShapeIterator(ly, topc, []))
l2n.threads = int(G.get('threads', '1'))
def poly(l, d, n): return l2n.make_polygon_layer(ly.layer(l, d), n)
m = [poly(34, 0, 'm1'), poly(36, 0, 'm2'), poly(42, 0, 'm3'), poly(46, 0, 'm4'), poly(81, 0, 'm5')]
v = [poly(35, 0, 'v1'), poly(38, 0, 'v2'), poly(40, 0, 'v3')]
v4 = poly(41, 0, 'v4'); ft = poly(75, 0, 'fusetop')
v4mim = v4 & ft; v4std = v4 - ft          # Via4 on a MIM top plate joins Metal5 to the plate, not to Metal4
l2n.register(v4mim, 'v4mim'); l2n.register(v4std, 'v4std')
for x in m+v+[ft, v4mim, v4std]: l2n.connect(x)
for k in range(3): l2n.connect(m[k], v[k]); l2n.connect(v[k], m[k+1])
l2n.connect(m[3], v4std); l2n.connect(v4std, m[4]); l2n.connect(m[4], v4mim); l2n.connect(v4mim, ft)
for k, (l, n) in enumerate(((34, 'm1'), (36, 'm2'), (42, 'm3'), (46, 'm4'), (81, 'm5'))):
    for d in (10, 0):        # label datatype, and texts drawn on the metal datatype itself
        tl = l2n.make_text_layer(ly.layer(l, d), f'{n}_txt{d}')
        l2n.connect(m[k], tl)
l2n.extract_netlist()
nl = l2n.netlist()
t_ext = time.time()-t0
ctop = nl.circuit_by_name(top)

# ---------------------------------------------------------------- pins of the black boxes, named
res = dict(gds=gds, top=top, ref=REF, boxes=len(boxes), extract_s=round(t_ext, 1), findings=[])
F = res['findings']
def names(net):
    return [x for x in (net.name or '').split(',') if x] if net is not None else []
box_pin = {}        # cell -> {pin id: [labels]}
NDANG = [0]
for b in boxes:
    c = nl.circuit_by_name(b)
    if c is None: continue
    want = set(ref[b]['pins']) if b in ref else None
    d = {}
    for p in c.each_pin():
        lab = names(c.net_for_pin(p.id()))
        d[p.id()] = [x for x in lab if want is None or x in want] or ['?'+('|'.join(lab) or 'unlabelled')]
    if want is not None:       # labelled block pins nobody touches from above still are pins (dangling at the level above)
        have = {x for lab in d.values() for x in lab}
        newp = []
        for net in list(c.each_net()):
            lab = [x for x in names(net) if x in want]
            if lab and net.pin_count() == 0 and not (set(lab) & have):
                p = c.create_pin(lab[0]); c.connect_pin(p, net); d[p.id()] = lab; have |= set(lab); newp.append(p)
        for sc in c.each_ref():
            par = sc.circuit()
            for p in newp:
                dn = par.create_net(); NDANG[0] += 1; dn.name = f'$open{NDANG[0]}'; sc.connect_pin(p, dn)
    box_pin[b] = d
    if want is not None:
        for net in c.each_net():           # two different pins of the block on one block net
            lab = [x for x in names(net) if x in want]
            if len(lab) > 1: res.setdefault('pins_joined_inside', {}).setdefault(b, []).append(lab)

# ---------------------------------------------------------------- (2) by name, with the manifest
if G.get('manifest'):
    man = json.load(open(RUN+G['manifest']))
    at = {}
    for i in man['instances']:
        if i.get('cell'): i['cell'] = REN.get(i['cell'], i['cell']); at[(i['cell'], db.Trans.from_s(i['trans']).disp.x, db.Trans.from_s(i['trans']).disp.y)] = i
    lay_net = {}      # top net id -> set of (inst, pin label)
    inst_of = {}
    unbound_sc = collections.Counter()
    for sc in ctop.each_subcircuit():
        cn = sc.circuit_ref().name
        tr = sc.trans
        i = at.get((cn, int(round(tr.disp.x/ly.dbu)), int(round(tr.disp.y/ly.dbu))))
        nm = i['name'] if i else f'<{cn}>'
        if not i: unbound_sc[cn] += 1
        for p in sc.circuit_ref().each_pin():
            net = sc.net_for_pin(p.id())
            if net is None: continue
            for lab in box_pin.get(cn, {}).get(p.id(), ['?'+cn]):
                lay_net.setdefault(net.cluster_id or net.name, set()).add((nm, lab))
    bound = {i['name']: i for i in man['instances'] if i.get('cell')}
    skip = set(filter(None, G.get('skip', '').split(',')))        # instances whose layout cell is a stand-in (pins not comparable)
    refnet = collections.defaultdict(set); unbound_inst = set()
    for name, nets, master in ref[top]['x']:
        pins = ref[master]['pins']
        if name not in bound or name in skip: unbound_inst.add(name); continue
        for p, n in zip(pins, nets): refnet[n].add((name, p))
    # pins joined by metal inside a block by design (inductor / tank terminals: a DC path, so the black-box view sees one
    # net): reference nets on such pins are merged before the comparison. Only joins both declared here and seen in
    # the layout (pins_joined_inside) count.
    DC_JOINED = {'pt_lna_deg': [('A', 'B')], 'pt_lna_ind': [('A', 'B')], 'pt_lc_qvco5': [('IN', 'IP'), ('QN', 'QP')]}
    seen = {(b, frozenset(g)) for b, gs in res.get('pins_joined_inside', {}).items() for g in gs}
    par = {}
    def fnd(x):
        while par.get(x, x) != x: x = par[x]
        return x
    for name, nets, master in ref[top]['x']:
        if name not in bound or name in skip: continue
        pn = dict(zip(ref[master]['pins'], nets))
        for a, b2 in DC_JOINED.get(master, []):
            if (master, frozenset((a, b2))) in seen and a in pn and b2 in pn: par[fnd(pn[a])] = fnd(pn[b2])
    if par:
        merged = collections.defaultdict(set)
        for n_, mem_ in refnet.items(): merged[fnd(n_)] |= mem_
        res['dc_joined_ref_nets'] = sorted('+'.join(sorted(n_ for n_ in refnet if fnd(n_) == r)) for r in merged if sum(fnd(n_) == r for n_ in refnet) > 1)
        refnet = merged
    where = {}
    for nid, mem in lay_net.items():
        for x in mem: where.setdefault(x, set()).add(nid)
    cnt = collections.Counter()
    full = {n for name, nets, master in ref[top]['x'] for n in nets}
    partial = {n for name, nets, master in ref[top]['x'] if name in unbound_inst for n in nets}
    for n in sorted(refnet):
        mem = refnet[n]
        ids = set().union(*[where.get(x, set()) for x in mem]) if mem else set()
        missing = sorted(x for x in mem if x not in where)
        foreign = sorted(x for i in ids for x in lay_net[i] if x not in mem and not x[0].startswith('<') and x[0] not in skip)
        internal = sorted(x for i in ids for x in lay_net[i] if x[1].startswith('?'))
        if len(mem) == 1 and not ids:
            cnt['single-pin here (other ends not bound to layout): not checkable'] += 1; continue
        st = []
        if missing or len(ids) > 1: st.append('open')
        if foreign: st.append('short')
        if internal: st.append('internal')
        if not st:
            cnt['match' if n not in partial else 'match on the bound pins (net also goes to unbound instances)'] += 1
        else:
            cnt['+'.join(st)] += 1
            if len(F) < 400: F.append(dict(net=n, status='+'.join(st), pins=len(mem), pieces=len(ids), not_connected=[f'{a}.{b}' for a, b in missing][:12],
                                           shorted_to=[f'{a}.{b}' for a, b in foreign][:12], internal=[f'{a}.{b}' for a, b in internal][:12]))
    stray = [sorted(f'{a}.{b}' for a, b in mem)[:8] for nid, mem in lay_net.items()
             if not any(x in y for y in refnet.values() for x in mem) and any(not a.startswith('<') for a, b in mem)]
    res.update(by_name=dict(cnt), ref_nets=len(full), nets_with_bound_pins=len(refnet), instances_bound=len(bound)-len(skip & set(bound)),
               instances_in_ref_not_bound=sorted(unbound_inst), layout_subcircuits_not_in_manifest=dict(unbound_sc),
               layout_nets_on_no_reference_net=stray[:40])
    bad = sum(v for k, v in cnt.items() if not k.startswith(('match', 'single-pin'))) + len(stray)
    res['by_name_clean'] = bad == 0

# ---------------------------------------------------------------- (1) KLayout compare on the black-box netlists
for b in boxes:
    c = nl.circuit_by_name(b)
    if c is None: continue
    for p in c.each_pin():
        lab = box_pin[b][p.id()]
        c.rename_pin(p.id(), lab[0])
    c.blank()
nl.purge()
rnl = db.Netlist(); rd = db.NetlistSpiceReader(); rnl.read(RUN+REF, rd)
for c in list(rnl.each_circuit()):
    if c.name.upper() != top.upper(): c.blank()
class Log(db.GenericNetlistCompareLogger):
    def __init__(s): super().__init__(); s.c = collections.Counter(); s.msgs = []
    def net_mismatch(s, a, b, msg=''): s.c['net_mismatch'] += 1; len(s.msgs) < 60 and s.msgs.append(f'net {a.name if a else None} / {b.name if b else None} {msg}')
    def pin_mismatch(s, a, b, msg=''): s.c['pin_mismatch'] += 1
    def subcircuit_mismatch(s, a, b, msg=''): s.c['subcircuit_mismatch'] += 1; len(s.msgs) < 60 and s.msgs.append(f'subcircuit {a.name if a else None} / {b.name if b else None} {msg}')
    def circuit_mismatch(s, a, b, msg=''): s.c['circuit_mismatch'] += 1; s.msgs.append(f'circuit {a.name if a else None} {msg}')
    def circuit_skipped(s, a, b, msg=''): s.c['circuit_skipped'] += 1; s.msgs.append(f'circuit skipped {a.name if a else None} {msg}')
    def match_nets(s, a, b): s.c['net_match'] += 1
    def match_subcircuits(s, a, b): s.c['subcircuit_match'] += 1
cmp = db.NetlistComparer(); log = Log()
ok = cmp.compare(nl, rnl, log)
res.update(klayout_compare=bool(ok), klayout_counts=dict(log.c), klayout_messages=log.msgs[:60], total_s=round(time.time()-t0, 1))
res['pass'] = bool(ok) and res.get('by_name_clean', True)
json.dump(res, open(outdir+'/lvs.json', 'w'), indent=1)
nl.write(outdir+'/layout_blackbox.cir', db.NetlistSpiceWriter())
print(f"LVS {top}: {'PASS' if res['pass'] else 'FAIL'} | KLayout compare {'match' if ok else 'MISMATCH'} {dict(log.c)} | by name {res.get('by_name')} | {res['total_s']} s")
for f in F[:12]: print('  ', f)
sys.exit(0 if res['pass'] else 1)
