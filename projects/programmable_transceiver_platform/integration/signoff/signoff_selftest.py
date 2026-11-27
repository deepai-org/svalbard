#!/usr/bin/env python3
"""Known-answer + negative controls of the signoff harness (cheap, no tool runs):   signoff_selftest.py <checked run dir>

Builds throw-away copies of a fully checked run (GDS symlinked, small result files copied), with the chip's stored
baseline set to that run's own counts, and requires: the unchanged copy passes; each injected fault reads as expected
(gate fail, count above baseline -> regressed, new rule class -> fail, stale result -> fail). Runs signoff.py
--collect-only --all on each copy. The chip comes from the run's check_conn.json (or SIGNOFF_CHIP)."""
import json, os, shutil, subprocess, sys, tempfile
SO = os.path.dirname(os.path.abspath(__file__)); SRC = os.path.abspath(sys.argv[1])
CHIP = os.environ.get('SIGNOFF_CHIP') or json.load(open(SRC + '/check_conn.json'))['chip']
FILES = ['place.log', 'route/route.log', 'route/routed.def', 'check_conn.json', 'lvs/chip/lvs.json', 'lvs/padsup.log',
         'shortcheck.json', 'grid_conn.txt', 'lvs/pt_chip_top.ref.spice', 'signoff/chip_smoke/summary.json'] + [f'drc/chip_{d}/{f}' for d in ('main', 'antenna', 'density') for f in ('counts.json', 'meta.txt')]
TMP = tempfile.mkdtemp(prefix='signoff_selftest_')
def make(name):
    r = f'{TMP}/{name}'; os.makedirs(r + '/chip')
    os.symlink(SRC + '/chip/pt_chip_top.gds', r + '/chip/pt_chip_top.gds')
    for f in FILES:
        os.makedirs(os.path.dirname(f'{r}/{f}'), exist_ok=True); shutil.copy(f'{SRC}/{f}', f'{r}/{f}')   # copies are newer than the GDS
    return r
def run(r, base):
    bf = f'{r}/base.json'; json.dump(base, open(bf, 'w'))
    env = dict(os.environ, SIGNOFF_BASELINE=bf)
    p = subprocess.run(['python3', SO + '/signoff.py', CHIP, r, '--collect-only', '--all'], env=env, capture_output=True, text=True)
    return p.returncode, {c['check']: c['status'] for c in json.load(open(r + '/signoff/signoff.json'))['checks']}
def edit(r, f, fn):
    p = f'{r}/{f}'; t = open(p).read(); n = fn(t); assert n != t, f'mutation of {f} did not apply'; open(p, 'w').write(n)

r0 = make('ref'); _, _ = run(r0, {'counts': {}})
base = {'counts': {m: cl for c in json.load(open(r0 + '/signoff/signoff.json'))['checks'] for m, cl in c.get('counts', {}).items()}}
ok = True
def expect(name, mut, want):
    global ok
    r = make(name); mut(r); rc, st = run(r, base)
    bad = {k: (st.get(k), v) for k, v in want.items() if st.get(k) != v}
    if name == 'clean': bad.update({k: v for k, v in st.items() if v not in ('pass', 'info', 'absent')})
    good = not bad and (rc == 0) == (name == 'clean')
    print(f'{"PASS" if good else "FAIL"} {name:<22} rc {rc} {bad if bad else ""}'); ok &= good

def lvs_short(r):
    d = json.load(open(r + '/lvs/chip/lvs.json'))
    d['findings'].append(dict(net='CLK_REF', status='short', pins=2, pieces=1, not_connected=[], shorted_to=['por.VDD'], internal=[]))
    d['by_name']['short'] = d['by_name'].get('short', 0) + 1; json.dump(d, open(r + '/lvs/chip/lvs.json', 'w'))
def drc_up(r, tag, rule, n):
    p = f'{r}/drc/chip_{tag}/counts.json'; d = json.load(open(p)); d['rules'][rule] = d['rules'].get(rule, 0) + n; d['total'] += n
    json.dump(d, open(p, 'w'))
def gc_join(r):
    edit(r, 'grid_conn.txt', lambda t: t.replace('"stub_nets": ["VDD"]', '"stub_nets": ["VDD", "VSS"]', 1))
def stale(r):
    os.utime(r + '/lvs/chip/lvs.json', (1, 1))
expect('clean', lambda r: None, {})
expect('drt up', lambda r: edit(r, 'route/route.log', lambda t: t + '\n[INFO DRT-0199]   Number of violations = 999.\n'), {'drt': 'regressed'})
expect('macro supply open', lambda r: edit(r, 'place.log', lambda t: t.replace('macro supply OK', 'macro supply VDD OPEN')), {'macro_supply': 'fail'})
expect('lvs real short', lvs_short, {'lvs_name': 'fail'})
expect('lvs stale', stale, {'lvs_name': 'fail'})
expect('padsup fail', lambda r: edit(r, 'lvs/padsup.log', lambda t: t.replace('PAD SUPPLY OK', 'PAD SUPPLY FAIL')), {'padsup': 'fail'})
expect('check_conn fail', lambda r: edit(r, 'check_conn.json', lambda t: t.replace('"pass_": true', '"pass_": false')), {'check_conn': 'fail'})
expect('shortcheck join', lambda r: edit(r, 'shortcheck.json', lambda t: t.replace('"vdd_vss_one_net": false', '"vdd_vss_one_net": true')), {'shortcheck': 'fail'})
expect('grid VDD/VSS join', gc_join, {'grid_conn': 'fail'})
expect('chip_smoke fail', lambda r: edit(r, 'signoff/chip_smoke/summary.json', lambda t: t.replace('"pass": true', '"pass": false')), {'chip_smoke': 'fail'})
expect('antenna up', lambda r: drc_up(r, 'antenna', sorted(base['counts']['antenna'])[0], 1), {'antenna': 'regressed'})
expect('drc new class', lambda r: drc_up(r, 'main', 'V1.1', 1), {'drc_main': 'fail'})
expect('drc other gds', lambda r: edit(r, 'drc/chip_main/meta.txt', lambda t: t.replace('sha256=', 'sha256=0')), {'drc_main': 'fail'})
shutil.rmtree(TMP, ignore_errors=True)
print('SIGNOFF SELFTEST', 'PASS' if ok else 'FAIL'); sys.exit(0 if ok else 1)
