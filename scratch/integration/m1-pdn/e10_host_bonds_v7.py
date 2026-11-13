#!/usr/bin/env python3
"""E10 (PD2): D2H rail question and bond options, dynamic side. Wired mode (D2H at 156.25 MHz, 116.8 mA at 8 pF), the
decap plan, v7 grid. Per option: D2H pk-pk on the host (south row) rail, host-row ground bounce against board ground,
D2H pk-pk at the macro and at core_bias; opt / nom / pess (matched sets). Static side: e7_static_v7.py vdd=.. gnd=.."""
import json, numpy as np
import model as M, core as C, loads as LD, pd2cfg as P2
P2.apply()
FH = np.array([78.125e6*k for k in range(1, 41)])
out, idig, ihost, m, rdir = LD.dc_loads('W', 'pd2w')
V0, G0 = list(M.VDD_PADS), list(M.VSS_PADS)
OPTS = {'baseline (8 supply, 10 ground)': ((), (), None), '+VDD pad 13': ((13,), (), None), '+VDD 13, +GND 4': ((13,), (4,), None),
        '+VDD 5, 13, +GND 4, 12': ((5, 13), (4, 12), None), '+VDD 40, +GND 38 (north)': ((40,), (38,), None),
        'D2H rail split on pads 18, 74 + GND 9, 19, 73, no added decap': ((), (), (18, 74, 9, 19, 73))}
def synth(lines, Zc, vi):
    f0 = min(l[2] for l in lines); t = np.arange(1024)/1024/f0; w = np.zeros(1024)
    for (ag, port, f, a, ae) in lines:
        k = int(np.searchsorted(FH, f)); w += (Zc[k, vi, C.PORTS.index(port)]*a*np.exp(2j*np.pi*f*t)).real
    return float((w.max()-w.min())*1e3)
res = {}
for name, (av, ag, hs) in OPTS.items():
    M.VDD_PADS = V0+[(x, 'X', 2.4) for x in av]; M.VSS_PADS = G0+list(ag); r = {}
    for s in ('opt', 'nom', 'pess'):
        kw = dict(host_split=hs) if hs else {}
        n, info, ports, vict = C.full(P2.pset(s), decap=P2.plan(), x_feed=P2.X_FEED, **kw)
        names, Zc, Zg = C.transfer(n, info, ports, vict, FH)
        dh = [l for l in LD.lines('W', idig, ihost, m, rdir, s) if l[0] == 'd2h']
        r[s] = dict(host_rail=synth(dh, Zc, names.index('host')), host_gnd_bounce=synth(dh, Zg, names.index('host')),
                    macro=synth(dh, Zc, names.index('dig')), core_bias=synth(dh, Zc, names.index('core_bias')))
    res[name] = r
    f = lambda k: ' / '.join(f'{r[s][k]:.0f}' for s in r)
    print(f"{name:62s} host rail {f('host_rail')} | host ground bounce {f('host_gnd_bounce')} | at macro {f('macro')} | at core_bias {f('core_bias')}  (mV pk-pk, opt / nom / pess)")
M.VDD_PADS, M.VSS_PADS = V0, G0
json.dump(res, open('out/e10_host_bonds_v7.json', 'w'), indent=1)
