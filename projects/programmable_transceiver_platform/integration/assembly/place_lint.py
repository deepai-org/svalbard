#!/usr/bin/env python3
"""Placement lint (run.sh, between place and route; host python, seconds):   place_lint.py <run dir>

Fails the run before routing on faults that are visible right after placement (coordinator 2026-11-27, after fpw-5 / fpw-6
were lost to diode placement):
  diode_in_pad      antenna diode overlapping a custom pad-family footprint (pads.json)
  diode_under_grid  antenna diode under grid Metal4 / Metal5 (pt_pdn.lef OBS, its 0.5 um wide-metal halo taken off)
  diode_in_slot     antenna diode under a hook slot (pt_pdn.lef PIN HK*)
  diode_in_reserve  antenna diode in a blocking floorplan reserve (the Metal1-3 DEF blockages); open plan channels are legal
                    (coordinator 2026-11-27: a diode costs channel routing almost nothing)
  grid_touch        place.json grid_touch (VDD / VSS grid metal touching) not empty
  fp_overlaps       floorplan.json overlaps not empty
  rail_diodes       an island rail (RAIL_*) with more than one diode
  macro_supply      place.log lacks 'macro supply OK'
  unconnectable     place.json unconnectable pins (must be 0)
  coverage          nets on the diode list with at least one placed diode, below ANT_COVER_MIN (default 0.95)
Prints one line per check and 'PLACE LINT PASS' / 'PLACE LINT FAIL'; writes place_lint.json; exit 1 on a fail.
Negative control: place_lint.py --selftest <run dir> injects one fault per check into a copy of the data and requires
each to fail."""
import json, os, re, sys, collections

DW, DH = 8.2, 6.5         # pt_antdiode outline (kl_place)


def load(run):
    man = json.load(open(f'{run}/place.json'))
    pads = json.load(open(f'{run}/pads.json'))['pads']
    fp = json.load(open(f'{run}/floorplan.json'))
    lef = open(f'{run}/lef/pt_pdn.lef').read()
    log = open(f'{run}/place.log').read() if os.path.exists(f'{run}/place.log') else ''
    obs = collections.defaultdict(list); slots = []
    body = lef[lef.rindex('  OBS'):]; lay = None
    for l in body.splitlines():
        m = re.match(r'\s*LAYER (\S+)', l)
        if m: lay = m[1]; continue
        m = re.match(r'\s*RECT (\S+) (\S+) (\S+) (\S+)', l)
        if m and lay in ('Metal4', 'Metal5'): obs[lay].append(tuple(map(float, m.groups())))
    for hn, b in re.findall(r'PIN (HK\d+)(.*?)END \1', lef, re.S):
        for r in re.findall(r'RECT (\S+ \S+ \S+ \S+)', b): slots.append(tuple(map(float, r.split())))
    return dict(man=man, pads=[tuple(f) for v in pads.values() for f in v['footprint']], reserves=[tuple(r) for n, r in fp.get('reserves', {}).items() if n != 'd2h_strip' and not n.startswith(('chan_', 'corridor', 'pocket'))],
                fp=fp,
                obs=obs, slots=slots, log=log)


def ov(a, b, g=0.0):
    return min(a[2], b[2]) - max(a[0], b[0]) > g and min(a[3], b[3]) - max(a[1], b[1]) > g


def lint(D, cover_min):
    man = D['man']; res = {}
    dio = [d for d in man.get('antenna_diodes', []) if d.get('placed')]
    box = {i: (d['at'][0], d['at'][1], d['at'][0] + DW, d['at'][1] + DH) for i, d in enumerate(dio)}
    def hits(rects, g=0.0):
        return [f"{dio[i]['net']}@{dio[i]['at']}" for i, b in box.items() if any(ov(b, r, g) for r in rects)]
    res['diode_in_pad'] = hits(D['pads'])
    res['diode_under_grid'] = hits(D['obs']['Metal4'] + D['obs']['Metal5'], 0.6)     # the OBS carries a 0.5 um halo
    res['diode_in_slot'] = hits(D['slots'])
    res['diode_in_reserve'] = hits(D['reserves'])
    rc = collections.Counter(d['net'] for d in dio if d['net'].startswith('RAIL_'))
    res['rail_diodes'] = [f'{n} x{c}' for n, c in rc.items() if c > 1]
    res['macro_supply'] = [] if 'macro supply OK' in D['log'] else ['place.log: no "macro supply OK"']
    res['unconnectable'] = [f"{u.get('inst')}.{u.get('pin')} ({u.get('why')})" for u in man.get('unconnectable', [])]
    res['grid_touch'] = [str(t) for t in man.get('grid_touch', [])]
    res['fp_overlaps'] = [str(t) for t in D['fp'].get('overlaps', [])]
    nets = collections.defaultdict(bool)
    for d in man.get('antenna_diodes', []): nets[d['net']] |= bool(d.get('placed'))
    need = len(nets); got = sum(nets.values()); cov = got / need if need else 1.0
    res['coverage'] = [] if cov >= cover_min else [f'{got} / {need} nets = {cov:.2f} < {cover_min:.2f}'] + [n for n, v in nets.items() if not v][:10]
    return res, cov, got, need


def main(run):
    cover_min = float(os.environ.get('ANT_COVER_MIN', '0.95'))
    res, cov, n, need = lint(load(run), cover_min)
    for k, v in res.items():
        print(f"{k:<18} {'ok' if not v else 'FAIL ' + str(len(v))} {'; '.join(v[:5])}")
    print(f'diode coverage {n} / {need} nets = {cov:.3f} (min {cover_min})')
    ok = not any(res.values())
    json.dump(dict(checks={k: v for k, v in res.items()}, coverage=round(cov, 4), placed=n, needed=need, cover_min=cover_min, pass_=ok),
              open(f'{run}/place_lint.json', 'w'), indent=1)
    print('PLACE LINT', 'PASS' if ok else 'FAIL'); return 0 if ok else 1


def selftest(run):
    import copy
    D0 = load(run); good = True
    pad = D0['pads'][0]; strap = (D0['obs']['Metal4'] or D0['obs']['Metal5'])[0]; slot = D0['slots'][0]
    res_ = D0['reserves'][0] if D0['reserves'] else None
    def put(D, at, net='X_TEST'):
        D['man'].setdefault('antenna_diodes', []).append(dict(net=net, pin='t.A', placed=True, at=list(at)))
    cases = {
        'diode_in_pad': lambda D: put(D, (pad[0] + 1, pad[1] + 1)),
        'diode_under_grid': lambda D: put(D, ((strap[0] + strap[2]) / 2 - 1, (strap[1] + strap[3]) / 2 - 1)),
        'diode_in_slot': lambda D: put(D, ((slot[0] + slot[2]) / 2 - 1, (slot[1] + slot[3]) / 2 - 1)),
        'rail_diodes': lambda D: (put(D, (1, 1), 'RAIL_TEST'), put(D, (1, 1), 'RAIL_TEST')),
        'macro_supply': lambda D: D.update(log=D['log'].replace('macro supply OK', 'macro supply VDD OPEN')),
        'unconnectable': lambda D: D['man'].setdefault('unconnectable', []).append(dict(inst='t', pin='p', why='test')),
        'coverage': lambda D: D['man']['antenna_diodes'].extend(dict(net=f'X{i}', pin='t.A', placed=False) for i in range(len(D['man']['antenna_diodes']) + 10)),
        'grid_touch': lambda D: D['man'].setdefault('grid_touch', []).append(['Metal5', 'VDD', 'VSS', 0, 0, 1, 1]),
        'fp_overlaps': lambda D: D['fp'].setdefault('overlaps', []).append(['a', 'b']),
    }
    if res_: cases['diode_in_reserve'] = lambda D: put(D, (res_[0] + 0.5, res_[1] + 0.5))
    for k, f in cases.items():
        D = copy.deepcopy(D0); f(D); r, *_ = lint(D, 0.95)
        hit = bool(r[k]); good &= hit; print(f"{'PASS' if hit else 'FAIL'} negative {k}")
    print('PLACE LINT SELFTEST', 'PASS' if good else 'FAIL'); return 0 if good else 1


if __name__ == '__main__':
    if sys.argv[1] == '--selftest': sys.exit(selftest(sys.argv[2]))
    sys.exit(main(sys.argv[1]))
