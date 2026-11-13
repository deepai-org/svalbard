"""Hierarchical terminal classifier for the full-chip SPICE binding.
For every subckt port: the set of device terminals reachable on that net inside the subckt,
as (kind, bulk) with bulk resolved to a port name of that subckt or '~int' (internal net).
kinds: gate, ndiff, pdiff (pfet S/D or p+/nwell diode anode; bulk = its n-well net), nwell (pfet bulk / diode cathode),
       res, cap, pbulk, ndio. A ':R' suffix marks a terminal reached through a resistor (series path, not blocked).
"""
import re, collections, sys
sys.setrecursionlimit(20000)
MOSN = re.compile(r'^(nfet_|nmos)', re.I)
MOSP = re.compile(r'^(pfet_|pmos)', re.I)


def parse(path):
    txt = open(path).read()
    txt = re.sub(r'\n\+\s*', ' ', txt)
    subs = {}
    for m in re.finditer(r'^\.subckt\s+(\S+)([^\n]*)\n(.*?)^\.ends', txt, re.M | re.S | re.I):
        ports = [p for p in m.group(2).split() if '=' not in p]
        subs[m.group(1)] = (ports, m.group(3).splitlines())
    return subs


class Classifier:
    def __init__(self, subs):
        self.subs = subs
        self.memo = {}

    def devices(self, name):
        """yield (kind, nodes, model) for each element line"""
        for l in self.subs[name][1]:
            t = l.split()
            if not t or t[0][0] in '*.':
                continue
            k = t[0][0].upper()
            nodes = [x for x in t[1:] if '=' not in x]
            yield k, t[0], nodes

    def cls(self, name):
        if name in self.memo:
            return self.memo[name]
        self.memo[name] = {}
        ports, _ = self.subs[name]
        pset = set(ports)
        acc = collections.defaultdict(set)
        res = []

        def B(n):
            return n if n in pset else '~int'
        for k, ref, nodes in self.devices(name):
            if not nodes:
                continue
            model = nodes[-1].lower() if k == 'X' else ''
            if k == 'M' or (k == 'X' and (MOSN.match(model) or MOSP.match(model))):
                if k == 'M':
                    d, g, s, b = nodes[:4]; model = nodes[4].lower()
                else:
                    d, g, s, b = nodes[:4]
                if MOSP.match(model) or model.startswith('p'):
                    acc[d].add(('pdiff', B(b))); acc[s].add(('pdiff', B(b))); acc[b].add(('nwell', None))
                else:
                    acc[d].add(('ndiff', None)); acc[s].add(('ndiff', None)); acc[b].add(('pbulk', None))
                acc[g].add(('gate', None))
            elif k == 'X' and nodes[-1] in self.subs:
                sub = nodes[-1]; sp = self.subs[sub][0]; c = self.cls(sub)
                m = dict(zip(sp, nodes[:-1]))
                for p, n in m.items():
                    for kind, b in c.get(p, ()):
                        if b is not None and b != '~int':
                            b = B(m.get(b, '~int'))
                        acc[n].add((kind, b))
            elif k == 'X':
                if 'diode_pd2nw' in model or 'pn_' in model:
                    acc[nodes[0]].add(('pdiff', B(nodes[1]))); acc[nodes[1]].add(('nwell', None))
                elif 'diode' in model or model.startswith('np_') or 'dnw' in model:
                    acc[nodes[0]].add(('pbulk', None)); acc[nodes[1]].add(('ndio', None))
                elif 'cap' in model or 'mim' in model:
                    for n in nodes[:-1]:
                        acc[n].add(('cap', None))
                elif 'pnp' in model or 'npn' in model:
                    for n in nodes[:-1]:
                        acc[n].add(('bjt', None))
                elif 'poly' in model or 'res' in model or 'rm' in model or model.startswith(('nplus', 'pplus', 'nwell')):
                    res.append((nodes[0], nodes[1]))
                    acc[nodes[0]].add(('res', None)); acc[nodes[1]].add(('res', None))
                else:
                    for n in nodes[:-1]:
                        acc[n].add(('other:'+model, None))
            elif k == 'R':
                res.append((nodes[0], nodes[1])); acc[nodes[0]].add(('res', None)); acc[nodes[1]].add(('res', None))
            elif k == 'C':
                acc[nodes[0]].add(('cap', None)); acc[nodes[1]].add(('cap', None))
            elif k == 'D':
                acc[nodes[0]].add(('pdiff', B(nodes[1]))); acc[nodes[1]].add(('nwell', None))
            elif k == 'L':
                res.append((nodes[0], nodes[1]))
        # propagate through resistors (series path): union-find over resistor ends
        par = {}
        def f(x):
            while par.get(x, x) != x:
                par[x] = par.get(par[x], par[x]); x = par[x]
            return x
        for a, b in res:
            par[f(a)] = f(b)
        grp = collections.defaultdict(list)
        for n in list(acc):
            grp[f(n)].append(n)
        for g, ns in grp.items():
            if len(ns) < 2:
                continue
            for n in ns:
                for o in ns:
                    if o == n:
                        continue
                    for kind, b in acc[o]:
                        if kind in ('res', 'cap') or kind.endswith(':R'):
                            continue
                        acc[n].add((kind+':R', b))
        self.memo[name] = {p: acc.get(p, set()) for p in ports}
        return self.memo[name]
