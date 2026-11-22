#!/usr/bin/env python3
"""mkspec_usb.py (esdopt/usb, copy of ../../txr/mkspec.py 2026-11-20; + resistor partners: a `res` terminal is named after the
traced net(s) at the other head of its poly piece, so that SPICE resistors map one to one).  Original docstring:
mkspec.py <gds> <out spec.json> <out devmap.json> NET[:max_step[:x1,y1,x2,y2]][!] ...   (run in the image via ../dock.sh)
netres spec for pad_txpad with every device terminal as an explicitly named terminal, plus a device map from the GDS:
each MOS gate (poly AND diffusion) with the terminals on its two sides, so that SPICE devices can be tied to terminals.
Terminal name = <kind>:<nets on the other side of the adjacent gates, '+'-joined>:<index>; the bond opening (37/0) terminal is
`bond`, otherwise the label is `pin`. NET! = keep only MOS terminals whose device has its other side on another listed net
(used for VSS). Groups = terminals sharing kind and partner; pairs: reference (bond/pin) to each group, and all group pairs."""
import sys, json, collections, klayout.db as k
sys.path.insert(0, '/work/hsfix'); import netres as n
g = n.Geo(sys.argv[1], None); d = g.dbu
args = []
for a in sys.argv[4:]:
    filt = a.endswith('!'); name, *rest = a.rstrip('!').split(':')
    args.append((name, float(rest[0]) if rest and rest[0] else 0.5, [float(v) for v in rest[1].split(',')] if len(rest) > 1 else None, filt))
pads = g.region(37); comp = g.region(n.COMP); poly = g.region(n.POLY); cont = g.region(n.CONT)
key = lambda b: (round(b[0], 3), round(b[1], 3))
owner = {}; raw = {}; ref = {}
for name, step, clip, filt in args:
    seeds = g.labels(name); assert seeds, name
    net, _ = n.trace(g, seeds, clip)
    raw[name] = n.auto_contacts(g, net, None, clip)
    for i, (kind, boxes) in enumerate(raw[name]):
        for b in boxes: owner[key(b)] = (name, i)
    ref[name] = None
    for p in pads.each():
        if not (net['M5'] & k.Region(p)).is_empty():
            b = p.bbox(); ref[name] = dict(name='bond', layer='M5', box=[b.left * d, b.bottom * d, b.right * d, b.top * d])
    if ref[name] is None and name in ('TERM_VCM', 'VSS', 'VDD'):
        m, x, y = seeds[0]; ref[name] = dict(name='pin', layer=m, box=[x - .25, y - .25, x + .25, y + .25])
# devices: gate polygons touching a diffusion piece of a listed net
sd = comp - poly; gates = poly & comp
mine = k.Region()
for b in owner: pass
cb = k.Region()
for name in raw:
    for kind, boxes in raw[name]:
        if kind in ('nmos', 'pmos'):
            for b in boxes: cb.insert(g.box(b))
pieces = sd.interacting(cb)
gsel = gates.sized(5).interacting(pieces)
partners = collections.defaultdict(list); devs = []
def piece_owner(p):
    c = cont.interacting(k.Region(p))
    for q in c.each():
        b = q.bbox(); o = owner.get(key([b.left * d, b.bottom * d]))
        if o: return o
    return None
for gp in gsel.each():
    bb = gp.bbox(); core = k.Region(gp).sized(-5)
    side = sd.interacting(k.Region(gp))
    own = [piece_owner(p) for p in side.each()]
    if len(own) != 2: raise SystemExit(f'gate at {bb.center().x * d},{bb.center().y * d}: {len(own)} diffusion sides')
    # width = extent of the gate along the edge shared with the diffusion: use the diffusion pieces' common extent
    pb = [p.bbox() for p in side.each()]
    horiz = abs(pb[0].center().x - pb[1].center().x) > abs(pb[0].center().y - pb[1].center().y)   # S/D left-right of the gate
    w, l = ((bb.height() - 10) * d, (bb.width() - 10) * d) if horiz else ((bb.width() - 10) * d, (bb.height() - 10) * d)
    devs.append(dict(x=round(bb.center().x * d, 3), y=round(bb.center().y * d, 3), w=round(w, 3), l=round(l, 3), sides=own))
    for a, b in ((0, 1), (1, 0)):
        if own[a]: partners[own[a]].append(own[b][0] if own[b] else '')
# resistor partners: other heads of the same poly piece, owned by another traced net
netm1 = {}
for name, step, clip, filt in args:
    nt, _ = n.trace(g, g.labels(name), clip); netm1[name] = nt['M1']
polyonly = poly - comp
for name in raw:
    for i, (kind, boxes) in enumerate(raw[name]):
        if kind != 'res': continue
        pc = polyonly.interacting(k.Region(g.box(boxes[0])))
        others = cont.interacting(pc) - cont.interacting(netm1[name])
        par = sorted({o for o in raw if o != name and not others.interacting(netm1[o]).is_empty()})
        partners[(name, i)].extend(par or ['?'])
nets = []; tname = {}
for name, step, clip, filt in args:
    terms = [ref[name]] if ref[name] else []; groups = collections.defaultdict(list); cnt = collections.Counter()
    for i, (kind, boxes) in enumerate(raw[name]):
        if kind not in ('nmos', 'pmos', 'res', 'ndiode', 'pdiode'): continue
        par = '+'.join(sorted(set(partners.get((name, i), []))))
        if filt and (kind not in ('nmos', 'pmos') or not par.replace('+', '')): continue
        gk = f'{kind}:{par}'; t = f'{gk}:{cnt[gk]}'; cnt[gk] += 1
        tname[(name, i)] = t; groups[gk].append(t)
        terms.append(dict(name=t, layer='M1', boxes=boxes, explicit=False))
    gn = sorted(groups); pairs = [[a, b] for i, a in enumerate(gn) for b in gn[i + 1:]]
    if ref[name]: pairs = [[ref[name]['name'], a] for a in gn] + pairs
    s = dict(name=name, max_step=step, min_cuts=2, min_width=1.0, terminals=terms, groups={a: dict(members=groups[a]) for a in gn}, pairs=pairs)
    if clip: s['clip'] = clip
    nets.append(s); print(name, 'terminals', len(terms), dict(cnt), 'ref', ref[name] and ref[name]['name'])
for dv in devs: dv['sides'] = [[o[0], tname.get(tuple(o))] if o else None for o in dv['sides']]
json.dump(dict(nets=nets), open(sys.argv[2], 'w'), indent=1)
json.dump(dict(devices=devs), open(sys.argv[3], 'w'))
print('devices', len(devs), collections.Counter((dv['w'], dv['l']) for dv in devs))
