"""D2H div2 + slow slew: required distance of the nearest host-comb harmonic from the channel edge, and a per-channel host-comb plan
(coordinator ruling 2). Pickup on channel (RQ-16, slow slew + PRBS, div2): -94.1 / -99.8 / -115.4 dBm (min / nom / max package bound).
Criterion (declared): after the baseband filter the spur is <= -100 dBm at the min bound -> filter attenuation >= 5.9 dB at the spur offset.
Filter: 5th-order Butterworth (bbfilter), A(f) = 10 log10(1 + (f / f3)^10); f3 per mode below. Host comb = div2 of the host clock;
ASSUMPTION (to be confirmed by timing / digital): the comb spacing can be set per channel from 75.0 to 80.0 MHz in 0.125 MHz steps."""
import json, math
NEED = -94.1 - (-100.0)
MODES = {'wifi20': dict(f3=10.5e6, half_bw=10e6, ch=[2412e6 + 5e6 * k for k in range(13)]),
         'ble': dict(f3=1.56e6, half_bw=1e6, ch=[2402e6 + 2e6 * k for k in range(40)]),
         'ieee802154': dict(f3=1.56e6, half_bw=1e6, ch=[2405e6 + 5e6 * k for k in range(16)])}
def off_needed(f3): return f3 * (10 ** (NEED / 10) - 1) ** 0.1
def nearest(fc, comb):
    n = round(fc / comb); return abs(fc - n * comb), n
combs = [75e6 + 0.125e6 * k for k in range(41)]
res = {}
for m, p in MODES.items():
    need = off_needed(p['f3']); rows = []
    for fc in p['ch']:
        d0, n0 = nearest(fc, 78.125e6)
        ok0 = d0 >= need
        alt = None if ok0 else max(combs, key=lambda c: nearest(fc, c)[0])
        rows.append(dict(ch_MHz=fc / 1e6, dist_78p125_MHz=round(d0 / 1e6, 3), ok_default=ok0,
                         alt_comb_MHz=None if ok0 else alt / 1e6, alt_dist_MHz=None if ok0 else round(nearest(fc, alt)[0] / 1e6, 3)))
    res[m] = dict(f3_MHz=p['f3'] / 1e6, offset_from_LO_needed_MHz=round(need / 1e6, 3), beyond_edge_MHz=round((need - p['half_bw']) / 1e6, 3),
                  all_planned=all(r['ok_default'] or (r['alt_dist_MHz'] or 0) >= need / 1e6 for r in rows),
                  n_default_clean=sum(r['ok_default'] for r in rows), n=len(rows), rows=rows)
    print(m, {k: v for k, v in res[m].items() if k != 'rows'})
json.dump(dict(criterion_db=NEED, assumption='comb 75-80 MHz in 0.125 MHz steps', modes=res), open('/home/ubuntu/svalbard/scratch/rf_rx/d2h/spur_plan.json', 'w'), indent=1)
