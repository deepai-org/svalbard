"""Steering buffer old (published) vs compact-array extraction: 2 pF load, 400 MHz square input, tt27/3.3, ss22/3.15, ff32/3.35."""
import sys, json, re
from pathlib import Path
import numpy as np
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads')
import stress_safe_clamp as s
W = Path(__file__).resolve().parent / 'eqw'
M = {'pub': Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads/generated/steering-buffer-compact/physical.spice'),
     'new': Path(__file__).resolve().parent / 'physical.spice'}
out = {}
for p, t, v in (('typical', 27, 3.3), ('ss', 22, 3.15), ('ss', 32, 3.15), ('ff', 22, 3.35), ('ff', 32, 3.35)):
    for tag, f in M.items():
        txt = f.read_text(); sub = re.search(r'^\.subckt (\S+) (.*)$', txt, re.M)
        ports = sub.group(2).split()
        conn = {'VDD': 'VDD', 'VSS': '0', 'IN': 'IN', 'OUT': 'OUT'}
        d = s.header(0) if False else None
        d = (f'* steer\n.include {s.SCRATCH}/transceiver-pad-pdk/ngspice/design.ngspice\n.lib {s.SCRATCH}/transceiver-pad-pdk/ngspice/sm141064.ngspice typical\n'
             f'.lib {s.SCRATCH}/transceiver-pad-pdk/ngspice/sm141064.ngspice res_typical\n.lib {s.SCRATCH}/transceiver-pad-pdk/ngspice/sm141064.ngspice diode_typical\n'
             f'.lib {s.SCRATCH}/transceiver-pad-pdk/ngspice/sm141064.ngspice mimcap_typical\n.temp 27\n' + txt +
             f'\nVDD VDD 0 {v}\nVIN IN 0 PULSE(0 {v} 1n 50p 50p 1.2n 2.5n)\nCL OUT 0 2p\nX1 ' + ' '.join(conn[q] for q in ports) + f' {sub.group(1)}\n')
        d = s.corner(d, p, t)
        name = f'{tag}_{p}_{t}'
        d += s.control(W, name, 'tran 1p 12n', 'v(IN) v(OUT) i(VDD)')
        x = s.run(W, name, d, timeout_s=1800)
        tt, vi, vo, idd = x[:, 0], x[:, 1], x[:, 2], x[:, 3]
        def cross(y, lev, rising, after):
            k = np.where((tt > after) & ((y[:-1] < lev) & (y[1:] >= lev) if rising else (y[:-1] > lev) & (y[1:] <= lev)) [:len(tt)-1] if False else None)
        def tcross(y, lev, rising, after):
            for i in range(len(tt) - 1):
                if tt[i] < after: continue
                if (rising and y[i] < lev <= y[i + 1]) or (not rising and y[i] > lev >= y[i + 1]):
                    return tt[i] + (lev - y[i]) * (tt[i + 1] - tt[i]) / (y[i + 1] - y[i])
        # 2nd period: IN rises at 3.5 ns, falls at 4.75 ns
        ri, fi = tcross(vi, v / 2, True, 3.4e-9), tcross(vi, v / 2, False, 4.7e-9)
        ro, fo = tcross(vo, v / 2, True, 3.4e-9), tcross(vo, v / 2, False, 3.4e-9)
        r10, r90 = tcross(vo, .1 * v, True, 3.4e-9), tcross(vo, .9 * v, True, 3.4e-9)
        f90, f10 = tcross(vo, .9 * v, False, 3.4e-9), tcross(vo, .1 * v, False, 3.4e-9)
        out[name] = dict(tpd_in_rise_ps=round((min(ro, fo) - ri) * 1e12, 1), out_rise_ps=round((r90 - r10) * 1e12, 1), out_fall_ps=round((f10 - f90) * 1e12, 1),
                         supply_mean_mA=round(float(-idd[tt > 2.5e-9].mean() * 1e3), 3))
        print(name, out[name], flush=True)
(Path(__file__).resolve().parent / 'equivalence.json').write_text(json.dumps(out, indent=1))
