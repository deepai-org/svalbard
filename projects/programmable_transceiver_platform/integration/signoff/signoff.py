#!/usr/bin/env python3
"""Signoff harness of one assembled chip (called by signoff.sh; see README.md "Signoff harness").

  signoff.sh <rf|wired> <ASM_RUN dir> [--all] [--collect-only] [--update-baseline [--provisional] --reason "..."]

Runs or collects every check on the run, cheap checks first, and writes <run>/signoff/signoff.json plus a table on
stdout. Each check reads pass / fail / regressed (or info = reported only, absent = optional hook not installed,
not run = skipped after a fail). A result already in the run is collected when it is newer than chip/pt_chip_top.gds
(DRC: when its meta.txt sha256 is the GDS's); otherwise the existing script is rerun (one heavy job at a time).
--collect-only never reruns: a stale or missing result is a fail. Fail fast: stops after the first fail unless --all.

Verdict per check: a gate (must hold) that does not hold -> fail. Counted metrics (marked with a baseline) are compared
with baseline/<chip>.json: a count above the baseline -> regressed; a class (rule, finding kind) with a nonzero count
that the baseline does not carry -> fail. Exit 0 only if no check is fail or regressed and a baseline exists.
--update-baseline writes baseline/<chip>.json from this run's counts (all checks run; refused if any gate fails);
commit it by pathspec with the reason."""
import json, os, re, subprocess, sys, time, hashlib, tempfile, shutil, datetime

SO = os.path.dirname(os.path.abspath(__file__)); INTEG = os.path.dirname(SO); ASM = INTEG + '/assembly'
ROOT = os.path.abspath(INTEG + '/../../..')
args = [a for a in sys.argv[1:]]
def opt(name):
    if name in args: args.remove(name); return True
    return False
ALL = opt('--all'); COLLECT = opt('--collect-only'); UPDATE = opt('--update-baseline'); PROV = opt('--provisional')
REASON = None
if '--reason' in args:
    i = args.index('--reason'); REASON = args[i+1]; del args[i:i+2]
if len(args) != 2 or args[0].replace('pt_', '') not in ('rf', 'wired'):
    sys.exit(__doc__)
CHIP = args[0].replace('pt_', ''); RUN = os.path.abspath(args[1])
if UPDATE:
    ALL = True
    if not REASON: sys.exit('--update-baseline needs --reason "<why the baseline moves>"')
GDS = RUN + '/chip/pt_chip_top.gds'
if not os.path.isfile(GDS): sys.exit(f'no {GDS}')
OUT = RUN + '/signoff'; os.makedirs(OUT, exist_ok=True)
BASEF = os.environ.get('SIGNOFF_BASELINE') or f'{SO}/baseline/{CHIP}.json'      # override: selftest only
BASE = json.load(open(BASEF)) if os.path.isfile(BASEF) else None

ENV = dict(os.environ, OMP_NUM_THREADS='1', ASM_RUN=RUN, SIGNOFF_RUN=RUN, SIGNOFF_CHIP=CHIP)
ENV.setdefault('KH_CONN', '1')      # the plan runs are KH_CONN=1 (FLOORPLAN_PLAN.md); check_conn skips without it
if 'ASM_DATA' not in ENV:           # worktree: data (PDK decks, untracked inputs) from the main checkout
    wl = subprocess.run(['git', '-C', ROOT, 'worktree', 'list', '--porcelain'], capture_output=True, text=True).stdout
    main = wl.split('\n')[0].replace('worktree ', '').strip()
    if main and os.path.realpath(main) != os.path.realpath(ROOT): ENV['ASM_DATA'] = main
GMT = os.path.getmtime(GDS)
def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''): h.update(b)
    return h.hexdigest()
GSHA = sha256(GDS)
def fresh(p): return os.path.isfile(p) and os.path.getmtime(p) >= GMT
def sh(cmd, log=None, **kw):
    """run one command (one heavy job at most); stdout to log file if given; returns (rc, text)"""
    t0 = time.time(); print(f'   .. {cmd if isinstance(cmd, str) else " ".join(cmd)}', flush=True)
    r = subprocess.run(cmd, shell=isinstance(cmd, str), env=ENV, capture_output=True, text=True, **kw)
    if log: open(log, 'w').write(r.stdout + r.stderr)
    print(f'   .. rc {r.returncode}, {time.time()-t0:.0f} s', flush=True)
    return r.returncode, r.stdout + r.stderr
class Fail(Exception): pass
def need(p, rerun, what):
    """collect p if fresh, else rerun (unless --collect-only); returns 'collected' or 'rerun'"""
    if fresh(p): return 'collected'
    if COLLECT: raise Fail(f'{what}: {os.path.relpath(p, RUN)} missing or older than the GDS (--collect-only)')
    if rerun is None: raise Fail(f'{what}: {os.path.relpath(p, RUN)} missing or stale and no script in this tree to rerun it')
    rerun()
    if not fresh(p): raise Fail(f'{what}: rerun wrote no {os.path.relpath(p, RUN)}')
    return 'rerun'
TOOL = lambda *c: [ASM + '/tool.sh', CHIP, '-c', *c]

# ------------------------------------------------------------------------------------------------- checks
# each returns dict(gates={name: bool}, counts={metric: {class: n}} (baseline-compared), info={...}, src=...)
def c_check_top():
    """chip-top connectivity regression (chips/check_top.py) on a clean export of HEAD (git archive), plus --selftest"""
    head = subprocess.run(['git', '-C', ROOT, 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', '-C', ROOT, 'status', '--porcelain', '--', 'projects/programmable_transceiver_platform/integration/chips',
                            'projects/programmable_transceiver_platform/spec', 'projects/programmable_transceiver_platform/rtl'],
                           capture_output=True, text=True).stdout.strip()
    T = tempfile.mkdtemp(prefix='signoff_top_')
    try:
        a = subprocess.run(f'git -C {ROOT} archive HEAD projects/programmable_transceiver_platform scratch/reviews/mode-walk '
                           f'scratch/chip-assembly-v6/run/floorplan-v6.json | tar -x -C {T}', shell=True, capture_output=True, text=True)
        if a.returncode: raise Fail('check_top: git archive of HEAD failed: ' + a.stderr[-300:])
        d = T + '/projects/programmable_transceiver_platform/integration/chips'
        _, o1 = sh(['python3', 'check_top.py', CHIP], cwd=d); _, o2 = sh(['python3', 'check_top.py', CHIP, '--selftest'], cwd=d)
    finally: shutil.rmtree(T, ignore_errors=True)
    open(OUT + '/check_top.log', 'w').write(o1 + o2)
    m = re.search(r'^SUMMARY pt_\w+ (.*) -> (PASS|FAIL)$', o1, re.M)
    if not m: raise Fail('check_top: no SUMMARY line (see signoff/check_top.log)')
    cnt = {k: int(v) for k, v in re.findall(r'(\w+)=(\d+)', m.group(1))}
    mw = re.findall(r'\(mode-walk (\S+) --selftest\) (PASS|FAIL)', o1)
    return dict(gates={'findings 0': sum(cnt.values()) == 0 and m.group(2) == 'PASS', 'selftest PASS': 'SELFTEST PASS' in o2,
                       'mode-walk selftests PASS': bool(mw) and all(v == 'PASS' for _, v in mw)},
                info={'head': head, 'tree dirty (ignored, HEAD checked)': bool(dirty), 'nonzero': {k: v for k, v in cnt.items() if v}},
                src='rerun (HEAD export)')

def c_drt():
    log = RUN + '/route/route.log'
    if not os.path.isfile(log): raise Fail('drt: no route/route.log')
    t = open(log, errors='replace').read(); v = re.findall(r'Number of violations = (\d+)', t)
    if not v: raise Fail('drt: no "Number of violations" in route.log')
    return dict(gates={'ROUTE DONE': 'ROUTE DONE' in t, 'routed.def written': os.path.isfile(RUN + '/route/routed.def')},
                counts={'drt': {'violations': int(v[-1])}}, src='collected route/route.log')

def c_macro_supply():
    t = open(RUN + '/place.log', errors='replace').read() if os.path.isfile(RUN + '/place.log') else ''
    m = re.search(r'macro supply ([A-Z ]*OPEN|OK)', t)
    if not m: raise Fail('macro_supply: place.log has no "macro supply" verdict (rerun place)')
    return dict(gates={'macro supply OK': m.group(1) == 'OK'}, info={'verdict': m.group(0)}, src='collected place.log')

def c_lvs_name():
    """LVS by name (top_lvs.py, the lvs stage of run.sh): zero real shorts; other non-match kinds baseline-counted"""
    p = RUN + '/lvs/chip/lvs.json'
    src = need(p, None if COLLECT else lambda: sh([ASM + '/run.sh', CHIP, 'lvs'], OUT + '/lvs_stage.log'), 'lvs_name')
    d = json.load(open(p)); bn = d.get('by_name')
    if bn is None: raise Fail('lvs_name: lvs.json has no by_name section (run without a manifest?)')
    real = []
    for f in d.get('findings', []):
        if 'short' not in f['status']: continue
        # benign: the macro's own unlabelled supply stripe of the same net (digital.?VDD on VDD; PDS-25, not a conn pin)
        bad = [x for x in f['shorted_to'] if x.split('.', 1)[-1].lstrip('?') != f['net']]
        if bad or len(f['shorted_to']) >= 12: real.append(f['net'])
    kinds = {k: v for k, v in bn.items() if not k.startswith(('match', 'single-pin'))}
    kinds = {k: v for k, v in kinds.items() if 'short' not in k}      # shorts: gated on the real ones above
    kinds['stray layout nets'] = len(d.get('layout_nets_on_no_reference_net', []))
    return dict(gates={'no real short': not real, 'every ref instance bound': not d.get('instances_in_ref_not_bound')},
                counts={'lvs_name': kinds},
                info={'match': bn.get('match', 0), 'real shorts': real, 'same-net macro stripe joins': [f['net'] for f in d.get('findings', [])
                      if 'short' in f['status'] and f['net'] not in real], 'klayout compare (reported)': d.get('klayout_compare')},
                src=src + ' lvs/chip/lvs.json')

def c_check_conn():
    p = RUN + '/check_conn.json'; s = ASM + '/check_conn.py'
    if os.path.isfile(s) and not COLLECT:
        rc, o = sh(['python3', s, CHIP], OUT + '/check_conn.log'); src = 'rerun'
        if 'skipped' in o: raise Fail('check_conn: skipped (KH_CONN=1 not set)')
    else: src = need(p, None, 'check_conn') + (' (check_conn.py not in this tree)' if not os.path.isfile(s) else '')
    if not fresh(p): raise Fail('check_conn: check_conn.json older than the GDS')
    d = json.load(open(p))
    return dict(gates={'pass': bool(d.get('pass_')), 'all counts 0': not any(d.get('counts', {}).values())},
                info={k: v for k, v in d.get('counts', {}).items()}, src=src + ' check_conn.json')

def c_padsup():
    p = RUN + '/lvs/padsup.log'; s = ASM + '/check_padsup.py'
    def rr(): os.makedirs(RUN + '/lvs', exist_ok=True); sh(TOOL('1', 'python3', '/asm/check_padsup.py'), p)
    src = need(p, rr if os.path.isfile(s) else None, 'padsup')
    t = open(p).read(); ok = 'PAD SUPPLY OK' in t
    return dict(gates={'PAD SUPPLY OK': ok and 'PAD SUPPLY FAIL' not in t},
                info={'pins ok': len(re.findall(r' ok$', t, re.M)), 'pins not ok': [l for l in t.split('\n') if re.match(r'^pad\S* \S+ \S+ (?!ok)', l)]},
                src=src + ' lvs/padsup.log')

def c_shortcheck():
    p = RUN + '/shortcheck.json'
    if fresh(p) and json.load(open(p)).get('dropped'): os.utime(p, (0, 0))      # a drop-cell diagnostic run is not the check
    src = need(p, lambda: sh(TOOL('1', 'python3', '/asm/kl_shortcheck.py'), OUT + '/shortcheck.log'), 'shortcheck')
    d = json.load(open(p))
    return dict(gates={'VDD and VSS not one net': not d['vdd_vss_one_net'], 'probes found both nets': d['vdd_nets'] > 0 and d['vss_nets'] > 0},
                info={'VDD probe nets': d['vdd_nets'], 'VSS probe nets': d['vss_nets']}, src=src + ' shortcheck.json')

def c_grid_conn():
    p = RUN + '/grid_conn.txt'
    if fresh(p) and 'MACRONET' not in open(p).read(): os.utime(p, (0, 0))       # a run without MACRONET=1 is not the check
    src = need(p, lambda: sh(TOOL('1', 'bash', '-c', 'MACRONET=1 python3 /repo/scratch/integration/m1-pdn/grid_conn.py'), p), 'grid_conn')
    t = open(p).read(); L = t.split('\n')
    if 'JSON' not in L: raise Fail('grid_conn: no JSON section in grid_conn.txt')
    d = json.loads(L[L.index('JSON') + 1])
    both = [x['id'] for x in d['pieces'] if len(x['stub_nets']) > 1]
    flp = [x['id'] for x in d['pieces'] if not x['n_stubs'] and x['pins']]
    stripes = re.findall(r'^MACRO (VDD|VSS) stripes: (\d+) (.*)$', t, re.M)
    stripe_ok = bool(stripes) and all(re.fullmatch(r"\{\(\('%s',\),\): \d+\}" % n, rest) for n, k, rest in stripes)
    return dict(gates={'no VDD/VSS join': not both, 'every block fed': not d['unfed'], 'no floating piece with a supply pin': not flp,
                       'macro stripes on their own net': stripe_ok, 'MACRONET=1 ran': 'MACRONET VDD' in t and 'MACRONET VSS' in t},
                info={'pieces': len(d['pieces']), 'floating pieces': sum(1 for x in d['pieces'] if not x['n_stubs']),
                      'unfed': len(d['unfed']), 'joined pieces': both, 'floating with pins': flp},
                src=src + ' grid_conn.txt')

def drc(deck, tag):
    d = f'{RUN}/drc/{tag}'
    def ok():
        try: return f'sha256={GSHA}' in open(d + '/meta.txt').read() and json.load(open(d + '/counts.json')).get('total') is not None
        except OSError: return False
    if ok(): return 'collected', json.load(open(d + '/counts.json'))
    if COLLECT: raise Fail(f'{tag}: drc/{tag} missing or not of this GDS (--collect-only)')
    sh([SO + '/drc/run_drc.sh', 'chip/pt_chip_top.gds', 'pt_chip_top', deck, tag, 'live', '2'], OUT + f'/{tag}.log')
    if not ok(): raise Fail(f'{tag}: the deck run wrote no counts for this GDS (see signoff/{tag}.log)')
    if os.path.isfile(d + '/report.lyrdb.gz'):
        r = subprocess.run(['python3', SO + '/drc/locate.py', d + '/report.lyrdb.gz'], env=dict(ENV, N='25'), capture_output=True, text=True)
        open(d + '/by_owner.txt', 'w').write(r.stdout)
    return 'rerun', json.load(open(d + '/counts.json'))
def c_density():
    src, c = drc('density', 'chip_density')
    return dict(gates={}, info={'total (before fill, reported only)': c['total'], 'rules': c['rules']}, src=src + ' drc/chip_density', report_only=True)
def c_antenna():
    src, c = drc('antenna', 'chip_antenna')
    return dict(gates={}, counts={'antenna': c['rules']}, info={'total': c['total']}, src=src + ' drc/chip_antenna')
def c_drc_main():
    src, c = drc('all,-antenna,-density,-cup', 'chip_main')
    return dict(gates={}, counts={'drc_main': c['rules']}, info={'total': c['total']}, src=src + ' drc/chip_main')

def c_lvs_bb():
    """device-level black-box LVS: hook for signoff/lvs/run_top_lvs_bb.sh <run> <out> (summary.json {pass, gds sha256})"""
    s = SO + '/lvs/run_top_lvs_bb.sh'
    if not os.path.isfile(s): return dict(gates={}, absent=True, info={'hook': 'signoff/lvs/run_top_lvs_bb.sh not in this tree'}, src='-')
    o = OUT + '/lvs_bb'; p = o + '/summary.json'
    cur = lambda: os.path.isfile(p) and GSHA in json.dumps(json.load(open(p)))
    src = 'collected'
    if not cur():
        if COLLECT: raise Fail('lvs_bb: no summary.json of this GDS (--collect-only)')
        sh([s, RUN, o], OUT + '/lvs_bb.log'); src = 'rerun'
        if not cur(): raise Fail('lvs_bb: no summary.json of this GDS after the run (see signoff/lvs_bb.log)')
    d = json.load(open(p))
    return dict(gates={'pass': d.get('pass') is True}, counts={'lvs_bb': d.get('findings_by_kind') or {}}, src=src + ' signoff/lvs_bb/summary.json')

CHECKS = [('check_top', c_check_top), ('drt', c_drt), ('macro_supply', c_macro_supply), ('check_conn', c_check_conn),
          ('lvs_name', c_lvs_name), ('padsup', c_padsup), ('shortcheck', c_shortcheck), ('grid_conn', c_grid_conn),
          ('density', c_density), ('antenna', c_antenna), ('drc_main', c_drc_main), ('lvs_bb', c_lvs_bb)]

# ------------------------------------------------------------------------------------------------- verdicts
def verdict(name, r):
    why = [f'gate "{g}" fails' for g, ok in r.get('gates', {}).items() if not ok]
    reg = []
    for metric, cl in r.get('counts', {}).items():
        b = (BASE or {}).get('counts', {}).get(metric)
        if b is None:
            if not UPDATE: why.append(f'{metric}: no baseline')
            continue
        for k, v in cl.items():
            if k not in b:
                if v > 0: why.append(f'{metric} {k}={v}: class not in baseline')
            elif v > b[k]: reg.append(f'{metric} {k}: {v} > baseline {b[k]}')
    if why: return 'fail', why + reg
    if reg: return 'regressed', reg
    if r.get('absent'): return 'absent', []
    if r.get('report_only'): return 'info', []
    return 'pass', []

rows = []; stop = False
print(f'signoff pt_{CHIP} {RUN}  gds sha256 {GSHA[:12]}  baseline {"none" if BASE is None else os.path.relpath(BASEF, ROOT) + (" (PROVISIONAL)" if BASE.get("provisional") else "")}')
for name, fn in CHECKS:
    if stop:
        rows.append(dict(check=name, status='not run', why=['stopped after the first fail (--all runs everything)'])); continue
    t0 = time.time(); print(f'-- {name}', flush=True)
    try: r = fn(); st, why = verdict(name, r)
    except Fail as e: r, st, why = {}, 'fail', [str(e)]
    rows.append(dict(check=name, status=st, why=why, counts=r.get('counts', {}), gates=r.get('gates', {}), info=r.get('info', {}),
                     src=r.get('src', ''), seconds=round(time.time() - t0)))
    if st == 'fail' and not ALL: stop = True

def short(r):
    c = r.get('counts') or {}
    if c: return '; '.join(f'{m} ' + (', '.join(f'{k} {v}' for k, v in sorted(cl.items()) if v) or '0') for m, cl in c.items())
    i = r.get('info') or {}
    return ', '.join(f'{k} {v}' for k, v in list(i.items())[:3])[:90]
bad = [r for r in rows if r['status'] in ('fail', 'regressed', 'not run')]
res = dict(chip=f'pt_{CHIP}', run=RUN, gds_sha256=GSHA, date=datetime.datetime.now().isoformat(timespec='seconds'),
           baseline=None if BASE is None else dict(file=os.path.relpath(BASEF, ROOT), provisional=BASE.get('provisional', False), source=BASE.get('source')),
           head=subprocess.run(['git', '-C', ROOT, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip(),
           all=ALL, collect_only=COLLECT, pass_=not bad and BASE is not None, checks=rows)
json.dump(res, open(OUT + '/signoff.json', 'w'), indent=1)
print(f'\n{"check":<13} {"status":<10} {"value":<70} source / why')
for r in rows:
    print(f'{r["check"]:<13} {r["status"]:<10} {short(r):<70} {"; ".join(r["why"]) if r["why"] else r.get("src", "")}')
print(f'SIGNOFF pt_{CHIP} {"PASS" if res["pass_"] else "FAIL"}  ({os.path.relpath(OUT, ROOT) if OUT.startswith(ROOT) else OUT}/signoff.json)')

if UPDATE:
    gfail = [r['check'] for r in rows if any(not ok for ok in r.get('gates', {}).values()) or (r['status'] == 'fail' and not r.get('gates'))]
    if gfail: sys.exit(f'baseline NOT updated: gates fail in {gfail}')
    nb = dict(chip=f'pt_{CHIP}', provisional=PROV, source=dict(run=os.path.relpath(RUN, ROOT) if RUN.startswith(ROOT) else RUN, gds_sha256=GSHA),
              reason=REASON, date=res['date'], counts={m: cl for r in rows for m, cl in r.get('counts', {}).items()})
    os.makedirs(os.path.dirname(BASEF), exist_ok=True); json.dump(nb, open(BASEF, 'w'), indent=1); open(BASEF, 'a').write('\n')
    print(f'baseline written: {BASEF}\n  commit it:  git commit -m "signoff baseline pt_{CHIP}: {REASON}" -- {os.path.relpath(BASEF, ROOT)}')
    sys.exit(0)
sys.exit(0 if res['pass_'] else 1)
