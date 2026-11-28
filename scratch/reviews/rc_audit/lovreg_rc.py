#!/usr/bin/env python3
"""pt_lo_vreg on its published extracted bench (scratch/lo-ap4/vreg2/ext.py one(), unchanged deck builder) for three views:
pub = published hierarchical C-only + the bench's hand gate R (as published); conly = flat C-only of the same GDS (no hand R);
rc = flat full R+C (rcx.py). Cases: operating settings tt/3.30 t6 and ss/3.15 t1, with the external capacitor, 25 mA load.
-> x/lo_vreg/bench.json"""
import sys, json, re
from pathlib import Path
V = Path('/home/ubuntu/svalbard/scratch/lo-ap4/vreg2'); sys.path.insert(0, str(V))
import b, ext, reg
X = Path(__file__).resolve().parent / 'x' / 'lo_vreg'
b.RUNS = X / 'runs'
ORDER = 'VIN VOUT VSS VREF EN BYP TRIM0 TRIM1 TRIM2 ATB_OUT ATB_G'
def flat(p):
    t = p.read_text()
    return re.sub(r'^\.subckt pt_lo_vreg .*$', '.subckt pt_lo_vreg ' + ORDER, t, count=1, flags=re.M, ) + '\n'
pub = ext.ext_netlist
views = dict(pub=pub, conly=lambda **k: flat(X / 'pt_lo_vreg.conly.spice'), rc=lambda **k: flat(X / 'pt_lo_vreg.rc.spice'))
out = {}
for c, t, vin, trim in (('tt', 27, 3.3, 6), ('ss', 32, 3.15, 1)):
    for vn, fn in views.items():
        ext.ext_netlist = fn
        r = ext.one(f'{vn}_{c}', c, t, vin, trim, reg.EXT_NOM)
        out[f'{vn}|{c}/{vin}/t{trim}|ext'] = r
        print(vn, c, 'vout', r['vout'], 'iq_uA', r['iq_uA'], 'lo21', r['lo21'], flush=True)
json.dump(out, open(X / 'bench.json', 'w'), indent=1, default=str)
