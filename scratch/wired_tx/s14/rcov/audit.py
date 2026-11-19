"""Parse full-coverage extraction x/<cell>/full.rc.spice, audit per THRESHOLDS.md. usage: audit.py <cell> -> x/<cell>.json"""
import sys, re, json, heapq
from pathlib import Path
from collections import defaultdict
HERE = Path(__file__).resolve().parent
FAST = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/wired_tx/generated/fast')
cell = sys.argv[1]
TIMING = re.compile(r'^(PH|PS)\w*$|^(CK|CLK)\w*$|^Q\d+$|^F\d+$|^STR\w*$|^(MAIN|POST)_[PN]$|^TAIL\w*$|^(XT|AP|AN)[MQ]?$|^X$|^(BM|BQ)\d+$')
SUP = re.compile(r'^(VDD|VSS|VSUBS)')
def val(x):
    m = re.match(r'^([-+\d.eE]+)([a-zA-Z]*)$', x)
    s = {'': 1, 'f': 1e-15, 'p': 1e-12, 'a': 1e-18, 'n': 1e-9, 'u': 1e-6, 'm': 1e-3, 'k': 1e3, 'meg': 1e6}
    return float(m.group(1)) * s[m.group(2).lower()]
def lines(t):
    return re.sub(r'\n\+', ' ', t).splitlines()
norm = lambda n: re.sub(r'_uq\d+', '', n.replace('/', '.'))
base = lambda n: re.sub(r'\.[nt]\d+$', '', norm(n))
drawnbase = lambda n: re.sub(r'#.*$', '', base(n))
def num(v):  # w=11u
    return val(v)

STUB0 = False
stub = [0.0]
def graph(L, base=base):
    ports = []
    adj = defaultdict(list); nodes = defaultdict(set)
    dev = defaultdict(lambda: {'ds': [], 'g': [], 'other': []})
    for l in L:
        tk = l.split()
        if not tk: continue
        if tk[0].lower() == '.subckt': ports = [norm(p) for p in tk[2:]]; continue
        if tk[0][0] == 'R':
            a, b, r = norm(tk[1]), norm(tk[2]), val(tk[3])
            if STUB0 and (re.search(r'\.t\d+$', a) or re.search(r'\.t\d+$', b)): stub[0] += r; r = 0.0
            adj[a].append((b, r)); adj[b].append((a, r))
            nodes[base(a)].add(a); nodes[base(b)].add(b)
        elif tk[0][0] == 'X':
            params = {k: v for k, v in (x.split('=', 1) for x in tk if '=' in x)}
            model = next((x for x in tk if x in ('nfet_03v3', 'pfet_03v3', 'nfet_06v0', 'pfet_06v0')), None)
            if model:
                d, g, s = norm(tk[1]), norm(tk[2]), norm(tk[3])
                W, L = num(params['w']) * 1e6, num(params['l']) * 1e6
                K = 2000.0 if model.startswith('n') else 4500.0
                ron = K * (L / 0.28) / W
                for n in (d, s): dev[n]['ds'].append((ron, f'{tk[0]} {model} W={W:g}u L={L:g}u'))
                dev[g]['g'].append(tk[0])
                for n in (d, g, s): nodes[base(n)].add(n)
            else:
                terms = [x for x in tk[1:] if '=' not in x][:-1]
                for n in terms: n = norm(n); dev[n]['other'].append(tk[0]); nodes[base(n)].add(n)
        elif tk[0][0] in 'D':
            for n in tk[1:3]: n = norm(n); dev[n]['other'].append(tk[0]); nodes[base(n)].add(n)

    return ports, adj, nodes, dev
full = lines((HERE / 'x' / cell / 'full.rc.spice').read_text())
ports, adj, nodes, dev = graph(full)
STUB0 = True
_, wadj, _, _ = graph(full)
STUB0 = False
# C: own extraction (all nets) and the cell's .ext.spice (named nets); used = max of the two
Cown = defaultdict(float)
for l in full:
    tk = l.split()
    if tk and tk[0][0] == 'C' and len(tk) >= 4:
        c = val(tk[3])
        for n in {base(tk[1]), base(tk[2])}: Cown[n] += c
C = defaultdict(float)
for l in lines((FAST / f'{cell}.ext.spice').read_text()):
    tk = l.split()
    if tk and tk[0][0] == 'C' and len(tk) >= 4:
        c = val(tk[3])
        for n in {norm(tk[1]), norm(tk[2])}: C[n] += c
# drawn-R set
drawn = set(); drawnR = defaultdict(list)
for l in lines((FAST / f'{cell}.rc.spice').read_text()):
    tk = l.split()
    if tk and tk[0][0] == 'R':
        for n in tk[1:3]: drawn.add(drawnbase(n))
def dij(adj, src, allowed):
    D = {s: 0.0 for s in src}; h = [(0.0, s) for s in src]
    while h:
        d, u = heapq.heappop(h)
        if d > D.get(u, 1e99): continue
        for v, r in adj[u]:
            if v in allowed and d + r < D.get(v, 1e99): D[v] = d + r; heapq.heappush(h, (d + r, v))
    return D
def rser(ns, adj, dev, pset):
    drv = [n for n in ns if dev[n]['ds']]
    lds = [n for n in ns if dev[n]['g'] or dev[n]['other'] or n in pset]
    ron = min((x for n in drv for x in dev[n]['ds']), default=None)
    if len(ns) == 1 or not any(adj[n] for n in ns):
        return 0.0, ron
    if drv and lds:
        D = dij(adj, drv, ns); return max((D.get(n, 0.0) for n in lds), default=0.0), ron
    src = [n for n in ns if n in pset] or drv or lds or list(ns)
    tg = lds or drv or list(ns)
    D = dij(adj, src, ns); R = max((D.get(n, 0.0) for n in tg), default=0.0)
    if not (pset & ns) and len(tg) > 1:
        R = max(max(dij(adj, [s], ns).get(x, 0.0) for x in tg) for s in tg[:50])
    return R, ron
pset = set(ports)
res = {}
for b, ns in nodes.items():
    if SUP.match(b.split('.')[-1]) or SUP.match(b): continue
    Rfull, ron = rser(ns, adj, dev, pset)
    R, _ = rser(ns, wadj, dev, pset)
    last = re.sub(r'#.*$', '', b.split('.')[-1])
    tim = bool(TIMING.match(last))
    c = max(C.get(b, 0.0), Cown.get(b, 0.0))
    a_ok = (ron is not None) and R < 0.05 * ron[0]
    b_ok = R * c < 2e-12
    ok = b_ok if tim else (a_ok or b_ok)
    res[b] = dict(R=round(R, 3), R_incl_stubs=round(Rfull, 3), C_fF=round(c * 1e15, 3), RC_ps=round(R * c * 1e12, 4), ron=round(ron[0], 1) if ron else None,
                  driver=ron[1] if ron else ('port' if b in pset else None), timing=tim, in_drawn=b in drawn,
                  a=a_ok, b=b_ok, ok=ok, c_found=b in C, C_ext_fF=round(C.get(b, 0.0)*1e15, 3), C_own_fF=round(Cown.get(b, 0.0)*1e15, 3))
dports, dadj, dnodes, ddev = graph(lines((FAST / f'{cell}.rc.spice').read_text()), base=drawnbase)
neg = {}
for b in sorted(drawn):
    if b in res and b in dnodes and not SUP.match(b.split('.')[-1]):
        Rd, _ = rser(dnodes[b], dadj, ddev, set(dports))
        if Rd > 0: neg[b] = dict(R_drawn=round(Rd, 2), R_full=res[b]['R'], ratio=round(res[b]['R'] / Rd, 3), R_full_incl_stubs=res[b]['R_incl_stubs'], ratio_incl_stubs=round(res[b]['R_incl_stubs'] / Rd, 3))
json.dump(dict(cell=cell, negative_control=neg, nets=res, drawn=sorted(drawn), ports=ports), open(HERE / 'x' / f'{cell}.json', 'w'), indent=0)
tot = len(res); ind = sum(v['in_drawn'] for v in res.values()); aud = tot - ind
fails = {k: v for k, v in res.items() if not v['in_drawn'] and not v['ok']}
print(cell, 'nets', tot, 'in_drawn', ind, 'audited', aud, 'fail', len(fails), 'noC', sum(not v['c_found'] for v in res.values()))
print('drawn names not found in full extraction:', len(drawn - set(res)), sorted(drawn - set(res))[:10])
for k, v in sorted(fails.items(), key=lambda kv: -kv[1]['RC_ps'])[:40]: print(k, v)
print('negative control (drawn net: R_drawn, R_full, ratio):')
for k, v in neg.items(): print(' ', k, v)
