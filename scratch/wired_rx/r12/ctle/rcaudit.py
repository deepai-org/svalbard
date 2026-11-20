"""rcaudit.py <C-only ext.spice> <R+C rc.ext.spice> <res.ext> [op.json]  -> rcaudit.json
(1) coverage: nets with a device terminal / of those carrying resistors in the R+C netlist;
(2) per-net capacitance cross-check R+C vs C-only (sum of all C touching the net, base names): max ratio (must be ~1.0);
(3) worst port/label-to-terminal series R per net (resistor graph, effective R) for the declared DC-path nets;
(4) if op.json (node voltages of the R+C CTLE, keys 'xc.<node>') is given: current in every resistor whose two rnodes sit at the
    same x,y (via / contact stack); per-cut current bound = I x R / 4.5 ohm (>= the true per-cut current of any via or contact
    stack), x1.3 design margin, against 0.58 mA/cut."""
import sys, re, json, collections
from pathlib import Path
import numpy as np
csrc, rsrc, resext = sys.argv[1:4]; opj = sys.argv[4] if len(sys.argv) > 4 else None
base = lambda n: re.sub(r'\.[nt]\d+$', '', n)
join = lambda p: re.sub(r'\n\+\s*', ' ', Path(p).read_text()).splitlines()


def cval(x):
    m = re.match(r'([-\d.eE+]+)([a-z]*)', x.lower()); return float(m.group(1)) * {'f': 1.0, 'p': 1e3, 'a': 1e-3, 'n': 1e6, 'u': 1e9, '': 1e15}[m.group(2)[:1]]


def ccount(lines):
    c = collections.Counter()
    for t in (l.split() for l in lines):
        if t and t[0][0] in 'Cc' and len(t) >= 4:
            v = cval(t[3]); c[base(t[1])] += v; c[base(t[2])] += v
    return c


C, R = join(csrc), join(rsrc)
cc, cr = ccount(C), ccount(R)
ratio = {n: cr[n] / cc[n] for n in cc if cc[n] > 0.5}
devnets = set()
for t in (l.split() for l in C):
    if t and t[0][0] == 'X':
        devnets |= {x for x in t[1:] if '=' not in x and not x.startswith(('nfet', 'pfet', 'ppoly'))}
res = [(w[1], w[2], float(w[3])) for w in (l.split() for l in R) if w and w[0][0] == 'R']
rnets = {base(p) for p, q, r in res}
sup = {'VSS', 'VDD_WIRE_SW'}
cov_all = sorted(devnets - sup)
covered = [n for n in cov_all if n in rnets]
# effective R from the base node to every terminal node of each net
term = collections.defaultdict(set)
for t in (l.split() for l in R):
    if t and t[0][0] == 'X':
        for x in t[1:]:
            if '=' not in x and x != base(x): term[base(x)].add(x)
bynet = collections.defaultdict(list)
for p, q, r in res: bynet[base(p)].append((p, q, r))
tnode = {n for v_ in term.values() for n in v_}
def effR(stub):
  reff = {}
  for net, rl in bynet.items():
    if not stub: rl = [(p, q, 1e-6 if (p in tnode or q in tnode) else r) for p, q, r in rl]
    nodes = sorted({p for p, q, r in rl} | {q for p, q, r in rl})
    if net not in nodes: continue
    ix = {n: i for i, n in enumerate(nodes)}; G = np.zeros((len(nodes),) * 2)
    for p, q, r in rl:
        i, j = ix[p], ix[q]; g = 1 / max(r, 1e-6); G[i, i] += g; G[j, j] += g; G[i, j] -= g; G[j, i] -= g
    k = [i for i in range(len(nodes)) if i != ix[net]]
    if not k: continue
    Z = np.linalg.pinv(G[np.ix_(k, k)]); d = dict(zip([nodes[i] for i in k], np.diag(Z)))
    tv = [d[n] for n in term[net] if n in d]
    if tv: reff[net] = dict(max=round(float(max(tv)), 2), mean=round(float(np.mean(tv)), 2), n=len(tv))
  return reff
reff = effR(True); rwire = effR(False)
out = dict(coverage=dict(nets_with_device_terminal=len(cov_all), with_resistors=len(covered), fraction=round(len(covered) / max(1, len(cov_all)), 3),
                         without=[n for n in cov_all if n not in rnets]),
           cap_check=dict(max_ratio=round(max(ratio.values()), 4), min_ratio=round(min(ratio.values()), 4),
                          worst=sorted(ratio.items(), key=lambda x: -abs(x[1] - 1))[:5]),
           r_eff_port_to_terminals=reff, r_wire_port_to_terminals=rwire)
# via / contact currents
if opj:
    xy = {}
    for t in (l.split() for l in Path(resext).read_text().splitlines()):
        if t and t[0] == 'rnode': xy[t[1].strip('"')] = (float(t[3]), float(t[4]))
    v = json.loads(Path(opj).read_text())
    gv = lambda n: v.get('xc.' + n.lower(), v.get('xc.' + base(n).lower()))
    vias = []
    for p, q, r in res:
        if p in xy and q in xy and xy[p] == xy[q] or (p in xy and q == base(q) and False):
            vp, vq = gv(p), gv(q)
            if vp is None or vq is None: continue
            i = abs(vp - vq) / r
            vias.append(dict(a=p, b=q, R=round(r, 3), I_mA=round(1e3 * i, 4), per_cut_bound_mA_x1p3=round(1.3e3 * i * r / 4.5, 4)))
    vias.sort(key=lambda x: -x['per_cut_bound_mA_x1p3'])
    out['vias'] = dict(n=len(vias), limit_mA=0.58, over=[x for x in vias if x['per_cut_bound_mA_x1p3'] > 0.58], worst=vias[:12])
Path('rcaudit.json').write_text(json.dumps(out, indent=1))
print(json.dumps({k: (v if k != 'r_eff_port_to_terminals' else {n: v[n] for n in sorted(v, key=lambda n: -v[n]['max'])[:25]}) for k, v in out.items()}, indent=0)[:6000])
