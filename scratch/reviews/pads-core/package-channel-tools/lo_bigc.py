"""Recompute the COB columns of lo.larger_padC (no generator on disk for scratch/cob/lo_bigC.json; formula = lo_term.leg).
Usage: lo_bigc.py old  -> check against scratch/cob/lo_bigC.json with the old geometry;  lo_bigc.py -> new geometry."""
import json, math, sys
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/pads-core/spec')
import placement as pl
old = json.load(open('/home/ubuntu/svalbard/scratch/cob/lo_bigC.json'))
g = json.load(open('/home/ubuntu/svalbard/scratch/cob/channel.json'))['geometry'] if sys.argv[1:] == ['old'] else pl.geo
def leg(p, f, C, R, place):
    M, _ = pl.chain_to(p, f, place, 0.0)
    return 2 * pl.deliver(pl.rev(M), 1 / (1j * 2 * math.pi * f * C + 1 / R))[1]
out = {}
for k, v in old.items():
    C = float(k.split('pF')[0][1:]) * 1e-12; R = float(k.split('R')[1])
    row = {kk: round(abs(leg(g['REF_IN'], 2.45e9, C, R, pp) + leg(g['REF_IN_N'], 2.45e9, C, R, pp)) / 2, 2)
           for kk, pp in (('cob_car30', 'car30mm'), ('cob_conn2', 'conn+2mm'))}
    row['old_1p5nH_only'] = v['old_1p5nH_only']          # geometry-independent reference column, carried over
    out[k] = row
if sys.argv[1:] == ['old']:
    print('reproduces old file:', out == old, [(k, out[k], old[k]) for k in out if out[k] != old[k]][:3])
else:
    json.dump(out, open('/home/ubuntu/svalbard/scratch/pads-core/spec/lo_bigC.json', 'w'), indent=1); print(out)
