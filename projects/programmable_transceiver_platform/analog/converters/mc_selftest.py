#!/usr/bin/env python3
"""Monte Carlo known-answer test for the converter benches (risk MOD-22, same method as analog/rf_rx/mc_selftest.py).

Every converter bench takes its model header from convkit.models(); CONV_MC_SEED=<n> adds sw_stat_mismatch=1 and the
seed.  The PDK fets_mm wrappers apply mismatch only to X instances of nfet_03v3/pfet_03v3, so this test checks:

1. Known answer: matched nfet_03v3 pair, W 10 / L 1 um, each diode-connected at 20 uA, dVgs = Vgs1 - Vgs2, written
   exactly as the converter netlists write MOS (X lines, convkit.Mos.spice()).  Expected sigma(dVgs) = 7.148 mV um /
   sqrt((L-0.15)(W+0.1)) = 2.45 mV (PDK par_vth; the current-factor term adds < 0.3 mV).  Pass: within +-20 % over N
   seeds (declared before the run).
2. Negative controls, each must give sigma < 0.05 mV: CONV_MC_SEED unset (mismatch off), and the same pair rewritten
   as M lines (the bypass MOD-22 describes).
3. Static scan: no published converter netlist (schematics and extracted netlists) holds an M line with a PDK MOS
   model, so nothing in the converter flow takes the bypass.

  python3 mc_selftest.py [N]      -> generated/mc-selftest.json, exit 0 only on PASS
"""
import json
import os
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'lib'))
import convkit as ck  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 60
WORK = HERE.parents[3] / 'scratch' / 'converters' / 'mc_selftest'
WORK.mkdir(parents=True, exist_ok=True)
pair = [ck.Mos('P1', 'nfet_03v3', 10, 1, 'd1', 'd1', 'VSS', 'VSS'), ck.Mos('P2', 'nfet_03v3', 10, 1, 'd2', 'd2', 'VSS', 'VSS')]
XLINES = [line for m in pair for line in m.spice()]
MLINES = [re.sub(r'^X(\S+)', r'M\1', line) for line in XLINES]
BODY = """VSS VSS 0 0
I1 vdd d1 20u
I2 vdd d2 20u
V1 vdd 0 3.3
.control
op
print v(d1)-v(d2)
.endc
.end
"""


def run(tag, seed, mline=False, mc=True):
    if mc:
        os.environ['CONV_MC_SEED'] = str(seed)
    else:
        os.environ.pop('CONV_MC_SEED', None)
    deck = f'* mc selftest {tag}\n' + ck.models('typical') + '\n'.join(MLINES if mline else XLINES) + '\n' + BODY
    os.environ.pop('CONV_MC_SEED', None)
    name = f'{tag}_{seed}.cir'
    r = ck.ngspice(WORK, name, deck, timeout=600)
    m = re.search(r'v\(d1\)-v\(d2\)\s*=\s*(\S+)', r.stdout)
    return float(m.group(1)) if m else None


def scan():
    bad, xs = [], 0
    files = sorted(HERE.glob('*.spice')) + sorted((HERE / 'generated').glob('*.ext.spice'))
    for f in files:
        for line in f.read_text().splitlines():
            if re.match(r'^M\S*\s.*\b[np]fet_0[356]v[03]', line, re.I):
                bad.append(f'{f.name}: {line[:80]}')
            elif re.match(r'^X\S*\s.*\b[np]fet_0[356]v[03]\b', line):
                xs += 1
    return dict(files=[f.name for f in files], x_mos_lines=xs, m_mos_lines=len(bad), examples=bad[:5])


res = {}
for tag, kw, n in (('mc', {}, N), ('neg_nomismatch', dict(mc=False), 10), ('neg_mline', dict(mline=True), 10)):
    v = [run(tag, k + 1, **kw) for k in range(n)]
    ok = [x for x in v if x is not None]
    res[tag] = dict(n_requested=n, n=len(ok), mean_mV=statistics.mean(ok) * 1e3 if ok else None,
                    sigma_mV=statistics.pstdev(ok) * 1e3 if ok else None)
    print(tag, res[tag], flush=True)
res['expected_sigma_mV'] = 2.45
res['limit'] = '+-20 % of expected; negative controls < 0.05 mV; no M-line PDK MOS in published netlists'
res['netlist_scan'] = scan()
res['image'] = ck.ANALOG_IMAGE
s = res['mc']['sigma_mV']
res['pass'] = bool(res['mc']['n'] == N and s is not None and abs(s / 2.45 - 1) <= 0.2
                   and res['neg_nomismatch']['n'] == 10 and res['neg_nomismatch']['sigma_mV'] < 0.05
                   and res['neg_mline']['n'] == 10 and res['neg_mline']['sigma_mV'] < 0.05
                   and res['netlist_scan']['m_mos_lines'] == 0 and res['netlist_scan']['x_mos_lines'] > 0)
(HERE / 'generated' / 'mc-selftest.json').write_text(json.dumps(res, indent=1) + '\n')
for f in WORK.glob('*'):
    f.unlink()
print('PASS' if res['pass'] else 'FAIL')
sys.exit(0 if res['pass'] else 1)
