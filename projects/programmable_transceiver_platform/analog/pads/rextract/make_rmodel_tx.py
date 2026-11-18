#!/usr/bin/env python3
"""R-aware simulation model of pad_txpad = the published Magic C-only model (physical.spice) + netres.py reduced networks.
(pattern: ../hsfix/make_rmodel.py)

    make_rmodel_tx.py <physical.spice> <typ|high> <out.spice> <scale> NET [NET ...]     (reads res.json, res_vss.json, devmap.json, spec.json here)

For every listed net each device terminal gets its own node `<NET>__<n>` and the exact reduced terminal network of that net
(one resistor per terminal pair, value x <scale>) is inserted; `bond` / `pin` stay the port node, and on a net without one
the first terminal keeps the original node name. scale = 1e-6 is the self-check (must reproduce the C-only model).
Device <-> terminal: MOS by the pair of nets on the two sides of each gate in the GDS (devmap.json from mkspec.py), checked
against W and L; devices with the same pair of nets are identical and taken in order. Poly resistors and diodes by net and kind.
Parasitic capacitors stay on the original node names. Not modelled: contact / diffusion resistance, gate-line metal, any net
not listed."""
import json, re, sys, collections
src, corner, out, scale = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]); NETS = sys.argv[5:]
D = json.load(open('res.json'))['nets']; D.update(json.load(open('res_vss.json'))['nets'])
traced = {n['name'] for n in json.load(open('spec.json'))['nets']}
txt = re.sub(r'\n\+\s*', ' ', open(src).read()).splitlines()
i0 = next(i for i, l in enumerate(txt) if l.startswith('.subckt combined_flat')); i1 = next(i for i in range(i0, len(txt)) if txt[i].startswith('.ends'))
body = [l.split() for l in txt[i0 + 1:i1]]
node = {}
for net in NETS:
    T = list(D[net]['terminals']); keep = [t for t in T if t in ('bond', 'pin')] or [next((t for t in T if t.startswith('res:')), T[0])]
    for k, t in enumerate(T): node[(net, t)] = net if t in keep else f'{net}__{k}'
um = lambda s: round(float(s[:-1]) * {'u': 1, 'm': 1e3, 'n': 1e-3}[s[-1]], 3)
pool = collections.defaultdict(list)
for dv in json.load(open('devmap.json'))['devices']:
    sides = [tuple(s) if s else (None, None) for s in dv['sides']]
    pool[(tuple(sorted(str(s[0]) for s in sides)), dv['w'], dv['l'])].append(sides)
pool2 = collections.defaultdict(list)
for net in NETS:
    for t in D[net]['terminals']:
        kd = t.split(':')[0]
        if kd in ('res', 'ndiode', 'pdiode'): pool2[(net, kd)].append(t)
cnt = collections.Counter()
for t in body:
    if not t or t[0][0] not in 'XD': continue
    nodes = [w for w in t[1:] if '=' not in w]; m = nodes[-1]; par = dict(w.split('=') for w in t if '=' in w)
    if m in ('nfet_03v3', 'pfet_03v3', 'nfet_06v0', 'pfet_06v0'):
        d, s = t[1], t[3]
        if d not in NETS and s not in NETS: continue
        key = (tuple(sorted(str(x if x in traced else None) for x in (d, s))), um(par['w']), um(par['l']))
        if not pool[key]: raise SystemExit(f'no GDS device left for {" ".join(t[:6])} key {key}')
        sides = pool[key].pop(0)
        for i in (1, 3):
            if t[i] in NETS:
                side = next(x for x in sides if x[0] == t[i]); sides = [x for x in sides if x is not side]
                if side[1] is None: raise SystemExit(f'{t[0]}: side on {t[i]} is not a terminal')
                t[i] = node[side]; cnt[f'mos {m}'] += 1
        assert t[2] not in NETS, t
    elif m.startswith('ppolyf') or m.startswith('diode'):
        kd = 'res' if m.startswith('ppolyf') else 'ndiode' if 'nd2ps' in m else 'pdiode' if 'pd2nw' in m else None
        for i in (1, 2):
            if t[i] in NETS:
                if not pool2[(t[i], kd)]: raise SystemExit(f'no {kd} terminal left on {t[i]} for {" ".join(t[:5])}')
                t[i] = node[(t[i], pool2[(t[i], kd)].pop(0))]; cnt[kd] += 1
    elif any(w in NETS for w in nodes[:-1]) and m != 'combined_flat':
        raise SystemExit('unclassified device on a listed net: ' + ' '.join(t))
left = {k: len(v) for k, v in pool.items() if v and any(n in NETS for n in k[0])}
left2 = {k: v for k, v in pool2.items() if v}
# VSS: only the tail sources are terminals; other VSS devices stay on the port node, so GDS devices with a VSS side may remain
left = {k: v for k, v in left.items() if not (set(k[0]) & set(NETS) <= {'VSS'})}
if left or left2: raise SystemExit(f'unused GDS terminals: {left} {left2}')
extra = []
for net in NETS:
    for a, b, r in D[net]['corners'][corner]['reduced_network']:
        na, nb = node[(net, a)], node[(net, b)]
        if na != nb and r < 1e8: extra.append(f'RNR{len(extra)} {na} {nb} {r * scale:.6g}')
new = txt[:i0 + 1] + [' '.join(t) for t in body] + [f'* netres.py resistances ({corner} metal x {scale}), nets {" ".join(NETS)}: {len(extra)} resistors'] + extra + txt[i1:]
open(out, 'w').write('\n'.join(new) + '\n')
print(out, dict(cnt), 'resistors', len(extra))
