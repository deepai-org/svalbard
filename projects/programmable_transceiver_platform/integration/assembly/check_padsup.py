#!/usr/bin/env python3
"""Pad supply gate (run.sh lvs stage, tool image): every supply pin of the custom pad families (DVDD / VDD on VDD, VSS / DVSS
on VSS) must be on the same extracted net as the core grid of that net (full Metal1-5 connectivity of chip/pt_chip_top.gds,
provider ring included). LVS by name does not bind the pad families and grid_conn once listed these pins as unfed.
Also every drawn provider tie (place.json io_ties direct) must extract onto its grid net.
Prints one line per pin and 'PAD SUPPLY OK' or 'PAD SUPPLY FAIL'; exit 1 on a fail (coordinator 2026-11-27)."""
import json, sys, klayout.db as db
ly = db.Layout(); ly.read('/run/chip/pt_chip_top.gds'); top = ly.cell('pt_chip_top')
names = [('M1', 34), ('V1', 35), ('M2', 36), ('V2', 38), ('M3', 42), ('V3', 40), ('M4', 46), ('V4', 41), ('M5', 81)]
l2n = db.LayoutToNetlist(db.RecursiveShapeIterator(ly, top, [])); lay = {}
for n, g in names:
    li = ly.find_layer(g, 0); lay[n] = l2n.make_layer(li, n) if li is not None else l2n.make_layer(n)
for a, v, b in (('M1', 'V1', 'M2'), ('M2', 'V2', 'M3'), ('M3', 'V3', 'M4'), ('M4', 'V4', 'M5')):
    for x in (a, v, b): l2n.connect(lay[x])
    l2n.connect(lay[a], lay[v]); l2n.connect(lay[v], lay[b])
l2n.extract_netlist()
man = json.load(open('/run/place.json')); MJ = json.load(open('/run/masters.json')); P = json.load(open('/run/pads.json'))
lm = {'Metal1': 'M1', 'Metal2': 'M2', 'Metal3': 'M3', 'Metal4': 'M4', 'Metal5': 'M5'}
def nid(lyr, x, y):
    n = l2n.probe_net(lay[lyr], db.DPoint(x, y)); return None if n is None else n.cluster_id
ref = {}
for h in man['hooks'][:300]:
    k = h['net'].split('__')[0]
    if k in ('VDD', 'VSS') and k not in ref:
        v = nid(lm[h['layer']], (h['piece'][0]+h['piece'][2])/2, (h['piece'][1]+h['piece'][3])/2)
        if v is not None: ref[k] = v
print('grid ids', ref); bad = 0 if set(ref) == {'VDD', 'VSS'} and ref['VDD'] != ref['VSS'] else 1
for pn, v in P['pads'].items():
    m = v['master']; t = db.DCplxTrans(db.Trans.from_s(v['trans']).to_dtype(0.001)) if False else None
    tr = db.Trans.from_s(v['trans']); o = MJ[m].get('origin', [0, 0])
    for pin, net in (('DVDD', 'VDD'), ('VDD', 'VDD'), ('VSS', 'VSS'), ('DVSS', 'VSS')):
        rs = MJ[m]['pins'].get(pin, [])
        res = set()
        for lnm, r in rs[:6]:
            b = tr * db.Box(round((r[0]+o[0])*1000), round((r[1]+o[1])*1000), round((r[2]+o[0])*1000), round((r[3]+o[1])*1000))
            c = b.center(); res.add(nid(lm.get(lnm, 'M1'), c.x/1000, c.y/1000))
        if rs:
            ok_ = ref.get(net) in res; print(pn, pin, net, 'ok' if ok_ else 'NOT ON GRID'); bad += 0 if ok_ else 1
# drawn provider ties (common.PAD_DIRECT_TIE, kl_place io_direct_ties): the tied pin must extract onto its grid net
# (coordinator 2026-11-27: the fpw-8 POR_BYPASS PD tie floated)
ntie = 0
for t in [t for t in man.get('io_ties', []) if t.get('direct')]:
    v = P['io'].get(t['site']); m = v['cell'] if v else None
    tr = db.Trans.from_s(v['trans']) if v else None; o = MJ.get(m, {}).get('origin', [0, 0])
    for pin in t['pins']:
        res = set()
        for lnm, r in MJ.get(m, {}).get('pins', {}).get(pin, [])[:4]:
            b = tr * db.Box(round((r[0]+o[0])*1000), round((r[1]+o[1])*1000), round((r[2]+o[0])*1000), round((r[3]+o[1])*1000))
            c = b.center(); res.add(nid(lm.get(lnm, 'M1'), c.x/1000, c.y/1000))
        ok_ = ref.get(t['net']) in res; ntie += 1
        print('direct tie', t['site'], pin, t['net'], 'ok' if ok_ else 'NOT ON GRID'); bad += 0 if ok_ else 1
print(f'direct ties checked {ntie}')
print('PAD SUPPLY OK' if bad == 0 else f'PAD SUPPLY FAIL ({bad})'); sys.exit(1 if bad else 0)
