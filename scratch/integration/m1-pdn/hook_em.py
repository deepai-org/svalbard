#!/usr/bin/env python3
"""hook_em.py <rf|wired> <run dir> [--gate] | hook_em.py --selftest
Hook nets (block supply pin -> grid slot, route/routed.def + place.json) of every supply user above 2 mA: resistance, drop
and EM at 85 C. Pins with an EM-clean drawn plate (place.json grid_plates, em_ok) are reported as plates, not hooks.
  * Widths from the DEF itself: a segment of a net with NONDEFAULTRULE <r> has the rule's width on its layer; a TAPER segment
    (and any net without a rule) has the tech default width (Metal1 0.23, Metal2-4 0.28, Metal5 0.44 um). Metal1 included.
  * Vias: the router uses single-cut tech vias and a hook is a series path, so every via carries the whole hook current;
    the cut count of a transition is the number of vias of that via layer within 1 um of each other (parallel cuts).
  * R: Rs per square (Metal1-4 0.090, Metal5 0.060 ohm/sq, tech LEF) + 4.5 ohm per cut, cuts of a transition in parallel.
  * Limits (tech LEF DCCURRENTDENSITY, scaled to 85 C by the 3.1 x the power spec uses): Metal 0.67 -> 2.09 mA/um,
    Metal5 1.5 -> 4.5 mA/um (x 3.0), Via 0.18 -> 0.56 mA per cut.
  * Current per pin group split evenly over its hooks. Currents: island_trunks.HEAVY (switch VDD at the island design
    current, load VDD / VSS worst) for the chip.
--gate: exit 1 if any hook is over a limit at 85 C. --selftest: a known-answer DEF (one hook, Metal4 100 um x 1 um +
one Via4) must give R 13.5 ohm, 1.0 mA/um, and fail on the via at 1 mA (single cut) and pass with two parallel cuts."""
import sys, re, json, collections, os, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
RS = {'Metal1': .09, 'Metal2': .09, 'Metal3': .09, 'Metal4': .09, 'Metal5': .06}
J85 = {'Metal1': 2.09, 'Metal2': 2.09, 'Metal3': 2.09, 'Metal4': 2.09, 'Metal5': 4.5}; V85 = 0.56; RV = 4.5
DEFW = {'Metal1': .23, 'Metal2': .28, 'Metal3': .28, 'Metal4': .28, 'Metal5': .44}


def heavy(ch, thr=0.5):
    """(inst, net) -> mA above thr: the power owner's per-pin table (chips/<ch>/pin_currents.json, worst DC at 85 C, isw VSS
    at their turn-off peak; pad supply pins and the macro excluded), else island_trunks.HEAVY"""
    t = os.path.join(HERE, f'../../../projects/programmable_transceiver_platform/integration/chips/{ch}/pin_currents.json')
    if os.path.exists(t):
        out = {}
        for r in json.load(open(t))['rows']:
            if r['kind'] != 'supply' or r['net'] not in ('VDD', 'VSS') or r['inst'] in ('digital', 'host') or r['inst'].startswith('pad_'): continue
            ma = max(r['avg_ma'], r.get('peak_ma') or 0) if r['master'].startswith('isw') and r['net'] == 'VSS' else r['avg_ma']
            if ma > thr: out[(r['inst'], r['net'])] = max(ma, out.get((r['inst'], r['net']), 0))
        return out
    p = os.path.join(HERE, '../../../projects/programmable_transceiver_platform/integration/assembly/island_trunks.py')
    src = open(p).read(); return eval(src[src.index('HEAVY = {')+8:src.index('\nPLATE_DROP_MV')])[ch]


def parse(deff):
    """net -> dict(rule, segs [(layer, length um, width um)], vias [(vialayer, x, y)])"""
    ndr = collections.defaultdict(dict); nets = {}; cur = None; rule = None; sect = None
    for l in open(deff):
        s = l.strip()
        if s.startswith('NONDEFAULTRULES'): sect = 'ndr'; continue
        if s.startswith('END NONDEFAULTRULES'): sect = None; continue
        if sect == 'ndr':
            m = re.match(r'- (\S+)', s)
            if m: rule = m.group(1)
            m = re.match(r'\+ LAYER (Metal\d) WIDTH (\d+)', s)
            if m: ndr[rule][m.group(1)] = int(m.group(2))/1000
            continue
        if s.startswith('NETS ') or s.startswith('SPECIALNETS'): sect = 'nets'; continue
        if s.startswith('END NETS'): sect = None; continue
        if sect != 'nets': continue
        m = re.match(r'- (\S+)', s)
        if m:
            cur = m.group(1); nets[cur] = dict(rule=None, segs=[], vias=[])
        if cur is None: continue
        m = re.search(r'NONDEFAULTRULE (\S+)', s)
        if m: nets[cur]['rule'] = m.group(1)
        t = re.search(r'(?:ROUTED|NEW)\s+(Metal\d)\s+(TAPER\s+)?(.*)', s)
        if not t: continue
        ln, taper, rest = t.group(1), bool(t.group(2)), t.group(3)
        pts = re.findall(r'\(\s*(\S+)\s+(\S+)(?:\s+\S+)?\s*\)', rest); P = []; px = py = None
        for x, y in pts:
            x = px if x == '*' else int(x); y = py if y == '*' else int(y); P.append((x, y)); px, py = x, y
        r_ = nets[cur]['rule']
        w = DEFW[ln] if (taper or not r_) else ndr.get(r_, {}).get(ln, DEFW[ln])
        for a, b in zip(P, P[1:]): nets[cur]['segs'].append((ln, (abs(a[0]-b[0])+abs(a[1]-b[1]))/1000, w))
        v = re.search(r'\)\s+(Via(\d)\S*)', rest)
        if v and P: nets[cur]['vias'].append(('Via'+v.group(2), P[-1][0]/1000, P[-1][1]/1000))
    return nets


def transitions(vias):
    """parallel cut groups: vias of one via layer within 1 um of each other"""
    groups = []
    for vl, x, y in vias:
        for g in groups:
            if g[0] == vl and abs(g[1]-x) <= 1 and abs(g[2]-y) <= 1: g[3] += 1; break
        else: groups.append([vl, x, y, 1])
    return groups


def hook_eval(net, I):
    segs = net['segs']; tr = transitions(net['vias'])
    R = sum(RS[ln]*L/max(w, 1e-3) for ln, L, w in segs) + sum(RV/g[3] for g in tr)
    jw = max((I/w/J85[ln], ln, w) for ln, L, w in segs if L > 0) if segs else (0, '-', 0)       # worst ratio to the 85 C limit
    jv = max((I/g[3]/V85, g[3]) for g in tr) if tr else (0, 0)
    return dict(R=R, wire_ratio=jw[0], wire_layer=jw[1], wire_w=jw[2], via_ratio=jv[0], via_cuts=jv[1], transitions=len(tr))


def report(ch, R_):
    place = json.load(open(R_+'place.json')); nets = parse(R_+'route/routed.def')
    plates = {k: v for k, v in place.get('grid_plates', {}).items() if 'error' not in v}      # drawn plates (em_ok from 2026-11-28 runs on)
    hooks = collections.defaultdict(list)
    for h in place['hooks']: hooks[(h['inst'], h['net'].split('__')[0])].append(h['net'])
    rows = []; over = 0
    for (inst, net), I in sorted(heavy(ch).items(), key=lambda kv: -kv[1]):
        key = f'{inst}.{net}'
        lst = hooks.get((inst, net), [])
        if key in plates and not lst:
            p = plates[key]; v_ = p.get('em_ok', None); bad = v_ is False or I/p['width_um'] > 2.09
            over += bad
            rows.append(f"{inst} | {net} | {I:.1f} | plate {p['width_um']} um | {p['drop_mV']} mV | {I/p['width_um']/2.09:.2f} x (plate) | {'-' if v_ is not False else 'plate vias short'} | {'OVER' if bad else 'ok' if v_ else 'ok (run predates em_ok)'}"); continue
        if not lst: rows.append(f'{inst} | {net} | {I:.1f} | no hook, no plate | - | - | - | CHECK'); continue
        ih = I/len(lst); ev = [hook_eval(nets.get(h, dict(segs=[], vias=[])), ih) for h in lst]
        rpar = 1/sum(1/max(e['R'], 1e-3) for e in ev)
        wr = max(ev, key=lambda e: e['wire_ratio']); vr = max(ev, key=lambda e: e['via_ratio'])
        bad = wr['wire_ratio'] > 1 or vr['via_ratio'] > 1
        over += bad
        rows.append(f"{inst} | {net} | {I:.1f} | {len(lst)} hook(s), {ih:.2f} mA each | {I*rpar:.0f} mV | {wr['wire_ratio']:.1f} x ({wr['wire_layer']} {wr['wire_w']} um) | "
                    f"{vr['via_ratio']:.1f} x ({vr['via_cuts']} cut) | {'OVER' if bad else 'ok'}")
    print(f'{ch} {R_}: supply pins > 0.5 mA (85 C limits: metal 2.09 / Metal5 4.5 mA/um, via 0.56 mA/cut)')
    print('inst | net | mA | hook / plate | drop | wire: worst ratio to limit | via: worst ratio | verdict')
    for r in rows: print(r)
    print(f'HOOK_EM {"FAIL" if over else "PASS"}: {over} over the 85 C limit')
    return over


def selftest():
    d = tempfile.mkdtemp()
    def write(cuts):
        vias = ''.join(f' NEW Metal4 ( {100000+i*620} 0 ) Via4_VH\n' for i in range(cuts))
        open(d+'/route/routed.def', 'w').write('NONDEFAULTRULES 1 ;\n- HOOK\n+ LAYER Metal4 WIDTH 1000\n;\nEND NONDEFAULTRULES\n'
            'NETS 1 ;\n- VSS__HK0 ( blk VSS ) ( pdn HK0 ) + USE SIGNAL + NONDEFAULTRULE HOOK\n'
            f'  + ROUTED Metal4 ( 0 0 ) ( 100000 0 )\n{vias} ;\nEND NETS\n')
    os.makedirs(d+'/route', exist_ok=True)
    ok = True
    for cuts, want_via_over in ((1, True), (2, False)):
        write(cuts); n = parse(d+'/route/routed.def')['VSS__HK0']; e = hook_eval(n, 1.0)
        exp_R = 0.09*100/1.0 + RV/cuts
        good = abs(e['R']-exp_R) < 1e-6 and abs(e['wire_ratio']-1.0/2.09) < 1e-6 and (e['via_ratio'] > 1) == want_via_over and e['via_cuts'] == cuts
        print(f'selftest cuts={cuts}: R {e["R"]:.3f} (want {exp_R:.3f}), wire ratio {e["wire_ratio"]:.3f} (want {1/2.09:.3f}), '
              f'via ratio {e["via_ratio"]:.2f} ({"over" if e["via_ratio"] > 1 else "ok"}, want {"over" if want_via_over else "ok"}): {"PASS" if good else "FAIL"}')
        ok &= good
    # taper: the same wire marked TAPER must take the 0.28 um default (negative control for the width parsing)
    open(d+'/route/routed.def', 'w').write('NONDEFAULTRULES 1 ;\n- HOOK\n+ LAYER Metal4 WIDTH 1000\n;\nEND NONDEFAULTRULES\nNETS 1 ;\n'
        '- VSS__HK0 ( blk VSS ) ( pdn HK0 ) + USE SIGNAL + NONDEFAULTRULE HOOK\n  + ROUTED Metal4 TAPER ( 0 0 ) ( 100000 0 ) ;\nEND NETS\n')
    e = hook_eval(parse(d+'/route/routed.def')['VSS__HK0'], 1.0); good = abs(e['wire_w']-0.28) < 1e-9 and e['wire_ratio'] > 1
    print(f'selftest taper: width {e["wire_w"]} um, ratio {e["wire_ratio"]:.2f} (want 0.28 um, over): {"PASS" if good else "FAIL"}')
    ok &= good
    print('HOOK_EM SELFTEST', 'PASS' if ok else 'FAIL'); return ok


if __name__ == '__main__':
    if '--selftest' in sys.argv: sys.exit(0 if selftest() else 1)
    over = report(sys.argv[1], sys.argv[2].rstrip('/')+'/')
    sys.exit(1 if ('--gate' in sys.argv and over) else 0)
