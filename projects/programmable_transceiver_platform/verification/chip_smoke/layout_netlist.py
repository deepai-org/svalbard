# KLayout (kl.sh): top-level netlist EXTRACTED from the chip GDS, for the chip smoke bench (--layout mode).
#   kl.sh <this> -rd gds=<path rel. to /run> -rd ref=<ref spice> -rd manifest=<json> -rd out=<spice> [-rd top=pt_chip_top]
#            [-rd flatten=<globs>] [-rd cut=<inst.pin>[,<inst.pin>...]] [-rd threads=1]
# Extraction as integration/signoff/lvs/top_lvs.py (Metal1..5, Via1..4, MIM top plate, labels; every direct child of the top
# cell, after the flatten list, is a black box keeping its pins; the pin name is the block's label on that net).
# Output: one SPICE netlist with the reference's instance names, masters and pin order, but every net is the EXTRACTED top-level
# net (named L<id>); nothing is taken from the reference's nets except which pad terminal is bonded to which package pin:
#   - a top port P (package pin) is the bond terminal of its pad cell (PAD / PAD_P / PAD_N / ASIG5V; VDD = the DVDD terminal of every
#     gf180mcu_fd_io__dvdd cell, VSS = the DVSS terminal of every gf180mcu_fd_io__dvss cell): the layout nets of those terminals
#     are merged into the port net P (the bond wires / board), everything else stays as extracted;
#   - a bond terminal that no top-level metal touches (a plain pad) is the port net itself;
#   - a reference pin that no top-level metal touches gets its own floating net (NC_<inst>_<pin>), so it is Z in the bench;
#   - a layout net on one instance pin only (a dangling stub) is named NC_L<id>, i.e. unconnected;
#   - the digital macro also gets its VDD / VSS grid pins (block labels VDD / VSS) on their extracted nets, so a macro on a dead
#     grid piece shows as unpowered.
# cut=inst.pin (negative control): before extraction, every top-level shape (after the flatten list) on the metal of that pin's
# terminal shape that touches it, every top-level via shape / via cell instance landing on it, is deleted (a GDS copy with that wire's metal erased).
# A summary is written next to the netlist (<out>.json): pins on several layout nets, unbound instances, shorts between ports.
import fnmatch, json, os, sys, time, collections
import klayout.db as db

t0 = time.time()
G = dict(globals())
RUN = '/run/'
top = G.get('top', 'pt_chip_top')
ly = db.Layout(); ly.read(RUN+G['gds'])
topc = ly.cell(top)
for pat in filter(None, G.get('flatten', 'retained_provider_ring,pt_pdn,pt_direct_land,pt_antdiode,pt_top_wiring,pt_island_bar,VIA_*').split(',')):
    for inst in list(topc.each_inst()):
        if fnmatch.fnmatch(inst.cell.name, pat): inst.flatten(1)

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
ref = read_spice(RUN+G['ref'])
man = json.load(open(RUN+G['manifest']))
at = {}
for i in man['instances']:
    if i.get('cell'):
        d = db.Trans.from_s(i['trans']).disp; at[(i['cell'], d.x, d.y)] = i['name']
def inst_name(cellname, disp_um=None, disp_dbu=None):
    if disp_um is not None: return at.get((cellname, int(round(disp_um.x/ly.dbu)), int(round(disp_um.y/ly.dbu))))
    return at.get((cellname, disp_dbu.x, disp_dbu.y))

ML = [(34, 0), (36, 0), (42, 0), (46, 0), (81, 0)]
VL = [(35, 0), (38, 0), (40, 0), (41, 0)]
res = dict(gds=G['gds'], ref=G['ref'], cut=[], findings=[])

# ---------------------------------------------------------------- negative control: erase the metal at one instance pin
for spec in filter(None, G.get('cut', '').split(',')):
    iname, pin = spec.split('.')
    hit = [x for x in topc.each_inst() if inst_name(x.cell.name, disp_dbu=x.trans.disp) == iname]
    assert len(hit) == 1, f'cut {spec}: instance {iname} not found once in the top cell ({len(hit)})'
    x = hit[0]; c = x.cell
    term = {}                   # metal index -> terminal region (top coordinates) on that metal
    for k, (l, d) in enumerate(ML):
        for dt in (10, 0):
            li = ly.find_layer(l, dt)
            if li is None: continue
            it = db.RecursiveShapeIterator(ly, c, li); it.shape_flags = db.Shapes.STexts
            while not it.at_end():
                s = it.shape()
                if s.is_text() and s.text_string == pin:
                    pt = it.trans() * s.text_pos
                    r = db.Region(db.RecursiveShapeIterator(ly, c, ly.layer(l, d))).merged()
                    r = r.interacting(db.Region(db.Box(pt.x-1, pt.y-1, pt.x+1, pt.y+1))).transformed(x.trans)
                    term[k] = (term.get(k, db.Region()) + r).merged()
                it.next()
    assert term, f'cut {spec}: no terminal shape labelled {pin} in {c.name}'
    nsh = nvi = 0
    for k, tr in term.items():
        # top-level shapes ON the terminal's metal, and vias landing on it from below / above (not wires merely crossing it)
        for (l, d) in [ML[k]] + ([VL[k-1]] if k > 0 else []) + ([VL[k]] if k < len(VL) else []):
            li = ly.find_layer(l, d)
            if li is None: continue
            sh = topc.shapes(li)
            kill = [s for s in sh.each_touching(tr.bbox()) if not s.is_text() and not db.Region(s.polygon).interacting(tr).is_empty()]
            for s in kill: sh.erase(s); nsh += 1
        lk = ly.find_layer(*ML[k])
        kv = [y for y in topc.each_touching_inst(tr.bbox()) if y.cell.name.lower().startswith('via')
              and not db.Region(db.RecursiveShapeIterator(ly, y.cell, lk)).transformed(y.trans).interacting(tr).is_empty()]
        for y in kv: y.delete(); nvi += 1
    term_area = sum(r.area() for r in term.values())*ly.dbu**2
    res['cut'].append(dict(pin=spec, cell=c.name, metals=sorted(k+1 for k in term), terminal_area_um2=round(term_area, 2), shapes_erased=nsh, via_instances_erased=nvi))

# ---------------------------------------------------------------- extraction (as top_lvs.py)
l2n = db.LayoutToNetlist(db.RecursiveShapeIterator(ly, topc, []))
l2n.threads = int(G.get('threads', '1'))
def poly(l, d, n): return l2n.make_polygon_layer(ly.layer(l, d), n)
m = [poly(34, 0, 'm1'), poly(36, 0, 'm2'), poly(42, 0, 'm3'), poly(46, 0, 'm4'), poly(81, 0, 'm5')]
v = [poly(35, 0, 'v1'), poly(38, 0, 'v2'), poly(40, 0, 'v3')]
v4 = poly(41, 0, 'v4'); ft = poly(75, 0, 'fusetop')
v4mim = v4 & ft; v4std = v4 - ft
l2n.register(v4mim, 'v4mim'); l2n.register(v4std, 'v4std')
for x in m+v+[ft, v4mim, v4std]: l2n.connect(x)
for k in range(3): l2n.connect(m[k], v[k]); l2n.connect(v[k], m[k+1])
l2n.connect(m[3], v4std); l2n.connect(v4std, m[4]); l2n.connect(m[4], v4mim); l2n.connect(v4mim, ft)
for k, (l, n) in enumerate(((34, 'm1'), (36, 'm2'), (42, 'm3'), (46, 'm4'), (81, 'm5'))):
    for d in (10, 0):
        tl = l2n.make_text_layer(ly.layer(l, d), f'{n}_txt{d}')
        l2n.connect(m[k], tl)
l2n.extract_netlist()
nl = l2n.netlist()
res['extract_s'] = round(time.time()-t0, 1)
ctop = nl.circuit_by_name(top)

def names(net): return [x for x in (net.name or '').split(',') if x] if net is not None else []
pinlab = {}       # block circuit -> {pin id: set(labels)}
def labels_of(cn):
    if cn not in pinlab:
        c = nl.circuit_by_name(cn); d = {}
        for p in c.each_pin(): d[p.id()] = set(names(c.net_for_pin(p.id())))
        pinlab[cn] = d
    return pinlab[cn]

# ---------------------------------------------------------------- instance pin -> extracted top net ids
pn = collections.defaultdict(set)        # (inst, label) -> {top net id}
bound = collections.Counter(); unbound = collections.Counter()
for sc in ctop.each_subcircuit():
    cn = sc.circuit_ref().name
    i = inst_name(cn, disp_um=sc.trans.disp)
    if i is None: unbound[cn] += 1; continue
    bound[i] += 1
    for pid, labs in labels_of(cn).items():
        net = sc.net_for_pin(pid)
        if net is None: continue
        for lab in labs: pn[(i, lab)].add(net.cluster_id)
T = ref[top]
BOND = {'gf180mcu_fd_io__dvdd': ('DVDD',), 'gf180mcu_fd_io__dvss': ('DVSS',), 'gf180mcu_fd_io__asig_5p0': ('ASIG5V',)}
def bond_pin(master, pin):
    if master in BOND: return pin in BOND[master]
    if master.startswith(('gf180mcu_fd_io__', 'selected_host_output', 'pad_')): return pin.startswith('PAD')
    return False
# union of layout nets: port P = all layout nets of its bond terminals
alias = {}
port_nets = collections.defaultdict(set)
for name, nets, master in T['x']:
    for p, n in zip(ref[master]['pins'], nets):
        if n in T['pins'] and bond_pin(master, p):
            for nid in pn.get((name, p), ()): port_nets[n].add(nid)
for P, ids in port_nets.items():
    for nid in ids:
        if nid in alias and alias[nid] != P:
            res['findings'].append(f'port short: package pins {alias[nid]} and {P} on one layout net (L{nid})'); continue
        alias[nid] = P
bonds = collections.Counter(n for name, nets, master in T['x'] for p, n in zip(ref[master]['pins'], nets) if n in T['pins'] and bond_pin(master, p))
for P in T['pins']:
    if not bonds[P]: res['findings'].append(f'port {P}: no pad-cell bond terminal in the reference')
def nname(nid): return alias.get(nid, f'L{nid}')

multi = []
out = [f'* GENERATED by verification/chip_smoke/layout_netlist.py from {G["gds"]} (extracted top level; reference = names only)']
MAC = 'pt_digital_macro'
for mst, d in ref.items():
    if mst == top: continue
    pins = d['pins'] + ([p for p in ('VDD', 'VSS') if p not in d['pins']] if mst == MAC else [])
    out.append(f'.subckt {mst} ' + ' '.join(pins)); out.append('.ends')
out.append(f'.subckt {top} ' + ' '.join(T['pins']))
nfloat = 0; notbound = []
for name, nets, master in T['x']:
    bonded = {p: n for p, n in zip(ref[master]['pins'], nets) if n in T['pins'] and bond_pin(master, p)}
    pins = ref[master]['pins'] + ([p for p in ('VDD', 'VSS') if p not in ref[master]['pins']] if master == MAC else [])
    if name not in bound: notbound.append(name)
    row = []
    for p in pins:
        ids = sorted(pn.get((name, p), ()))
        if not ids:
            if p in bonded: row.append(bonded[p]); continue        # a bond pad no top metal touches: the bond wire is the connection
            row.append(f'NC_{name}_{p}'); nfloat += 1; continue
        if len(ids) > 1:
            nm = sorted({nname(x) for x in ids})
            multi.append(f'{name}.{p}: {len(ids)} layout nets {nm[:6]}')
            # several pieces of one block pin: the bench takes the piece that is a port, else the first; listed in the summary
            ids = sorted(ids, key=lambda x: (x not in alias, x))
        row.append(nname(ids[0]))
    out.append(f'X{name} ' + ' '.join(row) + f' {master}')
# a layout net on exactly one instance pin and no port is a dangling stub: name it NC_ (unconnected, as the reference names them)
use = collections.Counter(n for l in out if l.startswith('X') for n in l.split()[1:-1])
ndang = 0
for k, l in enumerate(out):
    if l.startswith('X'):
        t = l.split()
        for j in range(1, len(t)-1):
            if t[j].startswith('L') and use[t[j]] == 1: t[j] = 'NC_'+t[j]; ndang += 1
        out[k] = ' '.join(t)
res['dangling_single_pin_nets'] = ndang
out.append('.ends')
open(RUN+G['out'], 'w').write('\n'.join(out)+'\n')
res.update(instances_ref=len(T['x']), instances_not_in_layout=notbound, layout_subcircuits_not_in_manifest=dict(unbound),
           floating_pins=nfloat, pins_on_several_layout_nets=multi, ports={P: sorted(f'L{x}' for x in ids) for P, ids in port_nets.items()},
           total_s=round(time.time()-t0, 1))
json.dump(res, open(RUN+G['out']+'.json', 'w'), indent=1)
print(f"layout_netlist: {len(T['x'])} instances ({len(notbound)} not in layout), {nfloat} reference pins untouched by top metal, "
      f"{len(multi)} pins on several layout nets, cut {res['cut']}, findings {res['findings'][:6]} | {res['total_s']} s")
