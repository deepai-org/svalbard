#!/usr/bin/env python3
"""R+C simulation model of pad_wirepad (published or option-A candidate) = Magic C extraction (physical.spice) + netres reduced networks.
(pattern: ../tx/mkmodel.py; device <-> terminal matching from mkspec_usb.py's device map and resistor partners)

    mkmodel_usb.py <physical.spice> <res dir> <typ|high> <out.spice> <scale>

Every traced net: each device terminal gets its own node <NET>__<k>; the exact reduced network (x scale) is inserted; `bond` / `pin`
keep the port node. MOS: matched by (W, L, nets on both sides); resistors by (net, net at the other head); diodes by kind (identical
fingers). Pad-site primaries (candidate): PAD-side terminals keep their own nodes, renamed PAD_x__dn<i> / PAD_x__up<i>; the nd2ps anodes of a
site move to VSS__a<x>, the pd2nw cathodes to DVDD__k<x>, each joined to the port (ring landing) by ONE resistor (netres SVSS_x / SVDD_x
pin|far, diode terminals shorted). scale 0.01 = self-check (must reproduce the C-only netlist's behaviour).
Parasitic capacitors stay on the port nodes. Not modelled: VSS / VDD / gate-line metal, contact / diffusion / poly-head resistance."""
import json, re, sys, collections
src, rdir, corner, out, scale = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5])
D = json.load(open(f'{rdir}/res.json'))['nets']
NETS = [n for n in D if not n.startswith('SV')]
site = any(n.startswith('SV') for n in D)
traced = {n['name'] for n in json.load(open(f'{rdir}/spec.json'))['nets']}
txt = re.sub(r'\n\+\s*', ' ', open(src).read()).splitlines()
i0 = next(i for i, l in enumerate(txt) if l.startswith('.subckt combined_flat')); i1 = next(i for i in range(i0, len(txt)) if txt[i].startswith('.ends'))
body = [l.split() for l in txt[i0 + 1:i1]]
node = {}
for net in NETS:
    T = list(D[net]['terminals']); keep = [t for t in T if t in ('bond', 'pin')] or [T[0]]
    for k, t in enumerate(T): node[(net, t)] = net if t in keep else f'{net}__{k}'
um = lambda s: round(float(s[:-1]) * {'u': 1, 'm': 1e3, 'n': 1e-3}[s[-1]], 3)
pool = collections.defaultdict(list)
for dv in json.load(open(f'{rdir}/devmap.json'))['devices']:
    sides = [tuple(s) if s else (None, None) for s in dv['sides']]
    pool[(tuple(sorted(str(s[0]) for s in sides)), dv['w'], dv['l'])].append(sides)
pool2 = collections.defaultdict(list)
for net in NETS:
    for t in D[net]['terminals']:
        kd = t.split(':')[0]
        if kd in ('ndiode', 'pdiode'): pool2[(net, kd)].append(t)
        if kd == 'res': pool2[(net, 'res', t.split(':')[1])].append(t)
cnt = collections.Counter(); sitek = collections.Counter()
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
    elif m.startswith('diode'):
        kd = 'ndiode' if 'nd2ps' in m else 'pdiode'
        on_pad = [w for w in t[1:3] if w in ('PAD_P', 'PAD_N')]
        if not on_pad:
            if any(w in NETS for w in t[1:3]): raise SystemExit('unclassified diode ' + ' '.join(t[:4]))
            continue
        leg = on_pad[0][-1]
        for i in (1, 2):
            if t[i] in ('PAD_P', 'PAD_N'):
                tt = pool2[(t[i], kd)].pop(0); nn = node[(t[i], tt)]
                if site and m in ('diode_nd2ps_06v0', 'diode_pd2nw_06v0') and 'area=22.5p' in ' '.join(t):
                    row = 'dn' if 'nd2ps' in m else 'up'; nn2 = f'PAD_{leg}__{row}{sitek[leg + row]}'; sitek[leg + row] += 1
                    node[(t[i], tt)] = nn2; nn = nn2
                t[i] = nn; cnt[kd] += 1
            elif t[i] == 'VSS' and site: t[i] = f'VSS__a{leg}'; cnt['site anode'] += 1
            elif t[i] == 'DVDD' and site: t[i] = f'DVDD__k{leg}'; cnt['site cathode'] += 1
        for j, w in enumerate(t):
            if w.startswith('pj=') and w.endswith('p'): t[j] = w[:-1] + 'u'; cnt['pj unit fixed'] += 1
    elif m.startswith('ppolyf'):
        orig = list(t)
        for i in (1, 2):
            if t[i] in NETS:
                other = orig[3 - i]; p = other if other in traced else '?'
                k_ = (t[i], 'res', p)
                if not pool2[k_]: raise SystemExit(f'no res terminal left on {t[i]} towards {p} for {" ".join(t[:5])}')
                t[i] = node[(t[i], pool2[k_].pop(0))]; cnt['res'] += 1
left = {k: len(v) for k, v in pool.items() if v and any(n in NETS for n in k[0])}
left2 = {k: v for k, v in pool2.items() if v}
if left or left2: raise SystemExit(f'unused GDS terminals: {left} {left2}')
extra = []
for net in NETS:
    for a, b, r in D[net]['corners'][corner]['reduced_network']:
        na, nb = node[(net, a)], node[(net, b)]
        if na != nb and r < 1e8: extra.append(f'RNR{len(extra)} {na} {nb} {r * scale:.6g}')
if site:
    for x in 'PN':
        extra.append(f"RSVSS_{x} VSS__a{x} VSS {D['SVSS_' + x]['corners'][corner]['resistance_ohm']['pin|far'] * scale:.6g}")
        extra.append(f"RSVDD_{x} DVDD__k{x} DVDD {D['SVDD_' + x]['corners'][corner]['resistance_ohm']['pin|far'] * scale:.6g}")
new = txt[:i0 + 1] + [' '.join(t) for t in body] + [f'* netres resistances ({corner} metal x {scale}): {len(extra)} resistors, {rdir}'] + extra + txt[i1:]
open(out, 'w').write('\n'.join(new) + '\n')
json.dump({f'{n}|{k}': v for (n, k), v in node.items()}, open(out + '.nodes.json', 'w'))
print(out, dict(cnt), 'resistors', len(extra))
