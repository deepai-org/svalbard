#!/usr/bin/env python3
"""Negative control of the chip smoke test, two runs on mutated copies of the top-level netlist; each must FAIL and name
exactly the broken wires:
  A  one c_* consumer pin unbound (KH-2 class) + the IE pin of the SPI_MOSI input pad unbound (KH-1 class)
     -> ctl_wire at that pin, pad_tie / pad_ie at that pad
  B  two trim bits swapped at their consumer (both still driven: only the register walk can see it)
     -> ctl_wire at both pins
Exit 0 only if both are caught.     selftest.py --chip rf|wired [smoke.py options]"""
import json, os, subprocess, sys
H = os.path.dirname(os.path.abspath(__file__))
args = sys.argv[1:]; chip = args[args.index('--chip')+1]
# probe wires: the trim buses tb_top_boundary.sv also probes
CTL = {'rf': 'c_lna_ct[2]', 'wired': 'c_ctle_peak[1]'}[chip]
SWAP = {'rf': ('lna', 'ct1', 'ct2', 'c_lna_ct[1]', 'c_lna_ct[2]'), 'wired': ('ctle', 'ctle_peak1', 'ctle_peak2', 'c_ctle_peak[1]', 'c_ctle_peak[2]')}[chip]
out = None
if '--out' in args: i = args.index('--out'); out = args[i+1]; del args[i:i+2]

def run(tag, spec):
    cmd = [sys.executable, H+'/smoke.py', *args, '--mutate', spec] + (['--out', f'{out}-mut{tag}'] if out else [])
    r = subprocess.run(cmd, capture_output=True, text=True)
    summ = next((l.split('-> ')[-1] for l in r.stdout.split('\n') if l.startswith('CHIP_SMOKE')), None)
    if not summ or not os.path.isfile(summ):
        print(f'{tag}: smoke.py wrote no summary\n' + r.stdout[-1500:] + r.stderr[-1500:]); return None, r.returncode
    return json.load(open(summ)), r.returncode

ok = True
S, rc = run('A', f'{CTL},pad:SPI_MOSI:IE')
if S:
    F = S['faults']; mut_pad = S['mutation'][1].split('.')[0]
    ctl_hit = [f for f in F if f['check'] == 'ctl_wire' and f'{CTL} ' in f['detail']]
    pad_hit = [f for f in F if f['check'] in ('pad_tie', 'pad_ie') and (f'pad {mut_pad} ' in f['detail'] or f'input pad {mut_pad}:' in f['detail'])]
    other = [f['check'] for f in F if f not in ctl_hit and f not in pad_hit]
    a_ok = rc != 0 and S['result'] == 'FAIL' and bool(ctl_hit) and bool(pad_hit)
    print(f'A mutations: {S["mutation"]}\n  caught c_* wire: {ctl_hit[:1]}\n  caught pad tie: {pad_hit[:2]}\n  consequential faults: {other}')
    print(f'  A {"CAUGHT" if a_ok else "MISSED"}'); ok &= a_ok
else: ok = False
inst, pa, pb, na, nb = SWAP
S, rc = run('B', f'swap:{inst}:{pa}:{pb}')
if S:
    F = S['faults']
    hit = {p for p in (pa, pb) for f in F if f['check'] == 'ctl_wire' and f' at {inst}.{p}=' in f['detail']}
    other = [f['check'] for f in F if f['check'] != 'ctl_wire']
    b_ok = rc != 0 and S['result'] == 'FAIL' and hit == {pa, pb}
    print(f'B mutation: {S["mutation"]}\n  caught at: {sorted(hit)}  ({sum(f["check"] == "ctl_wire" for f in F)} ctl_wire faults; others {other})')
    print(f'  B {"CAUGHT" if b_ok else "MISSED"}'); ok &= b_ok
else: ok = False
print(f'SELFTEST {"PASS" if ok else "FAIL"} {chip}')
sys.exit(0 if ok else 1)
