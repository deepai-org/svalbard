"""delay of the phase path PH k -> X k (falling X) against the trim code, schematic rev 3 (m9 bench, no pad)."""
import sys, json
import numpy as np
import m9
from chain import S
codes = [0, 1, 2, 4, 8, 15, 0, 7]
for c in sys.argv[1:]:
    o, w = m9.run(f'trim_{c}', c=c, nbits=48, pad=False, codes=codes, probes=[f'xmux.X{k}' for k in range(8)] + [f'PH{k}' for k in range(1, 8)] + ['xmux.Y5'])
    t = w['time']; vdd = o['vdd']; sw = m9.CORN[c]['swing']
    d = []
    for k in range(8):
        r = S.crossings(t, w[f'PH{k}'], th=sw / 2, rising=True); r = r[r > 6e-9]
        f = S.crossings(t, w[f'xmux.X{k}'], th=vdd / 2, rising=False)
        d.append(float(np.mean([f[f > x][0] - x for x in r[:4]])))
    base = (d[0] + d[6]) / 2
    y5 = w['xmux.Y5'][t > 6e-9]
    print(c, 'base delay ps', round(base * 1e12, 1), 'code:extra ps', {codes[k]: round((d[k] - base) * 1e12, 1) for k in (1, 2, 3, 4, 5, 7)},
          'Y at code 15: min/max V', round(float(y5.min()), 2), round(float(y5.max()), 2), flush=True)
