"""DC hysteresis of the detector's phase input stage (H1 inverter with a keeper K on its output, H2 inverter):
PH -> H1 -> n1, n1 -> H2 -> n2, n2 -> K -> n1.  Up and down DC sweeps; VH / VL = PH where n2 crosses VDD / 2.
    python3 hyst.py '{"h1":[1.0,2.5],"k":[0.6,1.5],"h2":[0.5,1.0]}'
"""
import sys, json
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / 's13'))
import m9  # noqa
from m9 import CH, tools, mux9
inv = mux9.inv


def one(sz, corner, temp, vdd, tag='hyst'):
    work = HERE / 'runs' / tag; work.mkdir(parents=True, exist_ok=True)
    res = {'ss': 'ss', 'ff': 'ff'}.get(corner, 'typical')
    L = ['* hyst', CH.pad_header(corner, temp, res), '.subckt st PH N2 VDD VSS']
    L += inv('H1', 'PH', 'N1', *sz['h1']) + inv('H2', 'N1', 'N2', *sz['h2']) + inv('K', 'N2', 'N1', *sz['k'])
    L += ['.ends', f'VDD VDD 0 {vdd}', 'VPH PH 0 0', 'X1 PH N2 VDD 0 st', '.options rshunt=1e12',
          '.control', f'dc VPH 0 {vdd} 0.005', 'wrdata up.txt v(N2) i(VDD)', f'dc VPH {vdd} 0 -0.005', 'wrdata dn.txt v(N2)', '.endc', '.end']
    (work / 'tb.sp').write_text('\n'.join(L) + '\n')
    tools.ngspice_host(work, 'tb.sp', timeout=300)
    u, d = np.loadtxt(work / 'up.txt'), np.loadtxt(work / 'dn.txt')
    vh = float(u[np.argmax(u[:, 1] > vdd / 2), 0])
    vl = float(d[np.argmax(d[:, 1] < vdd / 2), 0])
    k = np.argmin(abs(u[:, 0] - 1.35))
    return dict(corner=corner, temp=temp, vdd=vdd, VH=round(vh, 3), VL=round(vl, 3), i_1p35_ua=round(-float(u[k, 3]) * 1e6, 1))


if __name__ == '__main__':
    sz = json.loads(sys.argv[1])
    rows = [one(sz, c, t, v) for c in ('typical', 'ss', 'ff', 'sf', 'fs') for t in (0, 85) for v in (2.97, 3.63)]
    print(json.dumps(dict(sz=sz, VH_min=min(r['VH'] for r in rows), VH_max=max(r['VH'] for r in rows), VL_min=min(r['VL'] for r in rows),
                          VL_max=max(r['VL'] for r in rows), i_max_ua=max(r['i_1p35_ua'] for r in rows))), flush=True)
    if len(sys.argv) > 2:
        for r in rows:
            print(json.dumps(r))
