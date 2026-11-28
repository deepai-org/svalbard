#!/usr/bin/env python3
"""Pad supply gate (run.sh lvs stage, tool image): every supply pin of the custom pad families (DVDD / VDD on VDD, VSS / DVSS
on VSS) must be on the same extracted net as the core grid of that net (full Metal1-5 connectivity of chip/pt_chip_top.gds,
provider ring included). LVS by name does not bind the pad families and grid_conn once listed these pins as unfed.
Also every drawn provider tie (place.json io_ties direct) must extract onto its grid net.
Prints one line per pin and 'PAD SUPPLY OK' or 'PAD SUPPLY FAIL'; exit 1 on a fail (coordinator 2026-11-27)."""
import json, os, sys, klayout.db as db
sys.path.insert(0, '/asm'); import common as C
# A pad pin the conn puts on an island rail (pt_wired pad_hs_rx VDD on RAIL_wired_rx) must be on the same extracted net as
# that rail's switch output (isw VISL), and that switch's VDD pin must be on the grid VDD net, while VISL is not
# (coordinator 2026-11-27: a skip would hide an unfed pad).
# Negative control (always run, cheap: same extraction): each island-rail pad pin is also checked against the switches of
# every OTHER island; all of those must fail (a check that cannot tell rails apart would pass them). The full-chip
# rail-cut variant (flatten + erase) took > 40 min and was dropped. Prints NEG DETECTED / NEG MISSED; a miss fails.
# One-time rail-cut evidence (2026-11-27, coordinator): on a copy of fpw-8's chip GDS the top-level wiring / landing / bar
# shapes within 5 um of pad_hs_rx VDD (RAIL_wired_rx) were erased (14 shapes, no flatten; scratch/integration/fpw-8cut):
# 'pad_hs_rx VDD RAIL_wired_rx ISLAND RAIL NOT REACHED / NOT FED', PAD SUPPLY FAIL; uncut fpw-8: the pin passes. 10 min.
ly = db.Layout(); ly.read('/run/chip/pt_chip_top.gds'); top = ly.cell('pt_chip_top')
names = [('M1', 34), ('V1', 35), ('M2', 36), ('V2', 38), ('M3', 42), ('V3', 40), ('M4', 46), ('V4', 41), ('M5', 81)]
man = json.load(open('/run/place.json')); MJ = json.load(open('/run/masters.json')); P = json.load(open('/run/pads.json'))
NETS = json.load(open('/run/nets.json'))
ISL = {(i_, p_): n_ for n_, v_ in NETS.items() if n_ not in ('VDD', 'VSS') and v_.get('cls') != 'hook' for i_, p_ in v_['ends'] if i_ in P['pads']}
def shapes(inst, pin):
    if inst in P['pads']: v = P['pads'][inst]; m = v['master']
    else: v = man['blocks'][inst]; m = v['master']
    tr = db.Trans.from_s(v['trans']); o = MJ[m].get('origin', [0, 0])
    return [(lnm, tr * db.Box(round((r[0]+o[0])*1000), round((r[1]+o[1])*1000), round((r[2]+o[0])*1000), round((r[3]+o[1])*1000))) for lnm, r in MJ[m]['pins'].get(pin, [])[:6]]
l2n = db.LayoutToNetlist(db.RecursiveShapeIterator(ly, top, [])); lay = {}
for n, g in names:
    li = ly.find_layer(g, 0); lay[n] = l2n.make_layer(li, n) if li is not None else l2n.make_layer(n)
for a, v, b in (('M1', 'V1', 'M2'), ('M2', 'V2', 'M3'), ('M3', 'V3', 'M4'), ('M4', 'V4', 'M5')):
    for x in (a, v, b): l2n.connect(lay[x])
    l2n.connect(lay[a], lay[v]); l2n.connect(lay[v], lay[b])
l2n.extract_netlist()
lm = {'Metal1': 'M1', 'Metal2': 'M2', 'Metal3': 'M3', 'Metal4': 'M4', 'Metal5': 'M5'}
def nid(lyr, x, y):
    n = l2n.probe_net(lay[lyr], db.DPoint(x, y)); return None if n is None else n.cluster_id
ref = {}
for h in man['hooks'][:300]:
    k = h['net'].split('__')[0]
    if k in ('VDD', 'VSS') and k not in ref:
        v = nid(lm[h['layer']], (h['piece'][0]+h['piece'][2])/2, (h['piece'][1]+h['piece'][3])/2)
        if v is not None: ref[k] = v
ISLRES = []; NEGRES = []
FLOAT = {('pad_tlp', 'VDD'), ('pad_tlp', 'VSS')} if os.environ.get('CHIP') == 'wired' else set()
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
        if rs and (pn, pin) in FLOAT:
            # name-specific exception (coordinator 2026-11-27, option (c)): pad_tlp VDD / VSS float on this shuttle. Pass only
            # while each is on neither grid net, and VDD and VSS are not one net (LVS by name checks that nothing else joins)
            fid = set(nid(lm.get(l_, 'M1'), b.center().x/1000, b.center().y/1000) for l_, b in shapes(pn, pin)) - {None}
            other = set(nid(lm.get(l_, 'M1'), b.center().x/1000, b.center().y/1000) for l_, b in shapes(pn, 'VSS' if pin == 'VDD' else 'VDD')) - {None}
            ok_ = not (fid & {ref.get('VDD'), ref.get('VSS')}) and not (fid & other); bad += 0 if ok_ else 1
            print(pn, pin, net, 'floating (named exception, isolated)' if ok_ else 'FLOAT EXCEPTION VIOLATED (joined to a supply or to its pair)'); continue
        if rs and (pn, pin) in ISL:
            rail = ISL[(pn, pin)]; pid = set(nid(lm.get(l_, 'M1'), b.center().x/1000, b.center().y/1000) for l_, b in shapes(pn, pin)) - {None}
            sw = [i_ for i_, p_ in NETS[rail]['ends'] if p_ == 'VISL' and i_ in man['blocks']]
            # switches under an exposed island bar left the routed net (the bar joins their VISL): take them from common
            sw += [i_ for bd_ in C.ISLAND_BARS.get(os.environ.get('CHIP', ''), []) if bd_['net'] == rail for i_, p_ in bd_.get('vias', []) if p_ == 'VISL' and i_ in man['blocks'] and i_ not in sw]
            fed = []
            for s_ in sw:
                vi = set(nid(lm.get(l_, 'M1'), b.center().x/1000, b.center().y/1000) for l_, b in shapes(s_, 'VISL')) - {None}
                vd = set(nid(lm.get(l_, 'M1'), b.center().x/1000, b.center().y/1000) for l_, b in shapes(s_, 'VDD')) - {None}
                if pid & vi and ref.get('VDD') in vd and ref.get('VDD') not in vi: fed.append(s_)
            ok_ = bool(fed); bad += 0 if ok_ else 1; ISLRES.append(ok_)
            for orail in {n_ for n_ in NETS if n_.startswith('RAIL_') and n_ != rail}:
                osw = [i_ for i_, p_ in NETS[orail]['ends'] if p_ == 'VISL' and i_ in man['blocks']] + [i_ for bd_ in C.ISLAND_BARS.get(os.environ.get('CHIP', ''), []) if bd_['net'] == orail for i_, p_ in bd_.get('vias', []) if p_ == 'VISL' and i_ in man['blocks']]
                for s_ in osw:
                    vi = set(nid(lm.get(l_, 'M1'), b.center().x/1000, b.center().y/1000) for l_, b in shapes(s_, 'VISL')) - {None}
                    NEGRES.append(not (pid & vi))
            print(pn, pin, rail, f'ok (island rail, fed through {",".join(fed)})' if ok_ else f'ISLAND RAIL NOT REACHED / NOT FED (switches {sw})'); continue
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
det = (not ISLRES) or (bool(NEGRES) and all(NEGRES))
print('NEG DETECTED' if det else 'NEG MISSED', f'(island-rail pad pins against {len(NEGRES)} other-island switches)'); bad += 0 if det else 1
print('PAD SUPPLY OK' if bad == 0 else f'PAD SUPPLY FAIL ({bad})'); sys.exit(1 if bad else 0)
