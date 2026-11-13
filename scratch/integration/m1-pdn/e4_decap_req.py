#!/usr/bin/env python3
"""E4: how much decap, and where. Steady-state pk-pk ripple from the digital macro (78.125 MHz charge packets) and from
D2H at the macro, core_bias and the pll/LO island tap, versus added decap (MOS tiles) placed (a) in/at the macro,
(b) spread over the analog core, (c) half/half. Matched bounds: opt source on the opt network, nom on nom, pess on pess.
Hand check: pk-pk ~ Q_cycle (1 - tw/T) / C_total when the anti-resonance is below the clock."""
import json, numpy as np
import model as M, core as C, loads as LD
mo = 'wired_onchip_pll'
out, idig, ihost, m, rdir = LD.dc_loads(mo, 'evid+')
res = {}
F = np.array([78.125e6*k for k in range(1, 41)])
def synth(lines, Zc, vi):
    f0 = min(l[2] for l in lines); t = np.arange(1024)/1024/f0; w = np.zeros(1024)
    for (ag, port, f, a, ae) in lines:
        k = int(np.searchsorted(F, f)); w += (Zc[k, vi, C.PORTS.index(port)]*a*np.exp(2j*np.pi*f*t)).real
    return float((w.max()-w.min())*1e3)
print('added nF | where | digital pk-pk at macro / core_bias / qvco tap (mV)  opt | nom | pess   || D2H pk-pk at macro opt|nom|pess')
for where in ('macro', 'spread', 'half'):
    for c in (0, 1, 2, 3, 4, 6, 8, 12):
        row = {}
        for b in ('opt', 'nom', 'pess'):
            d = {'macro': C.decap_plan('digital', c), 'spread': C.decap_plan('uniform', c),
                 'half': C.decap_plan('digital', c/2)+C.decap_plan('uniform', c/2)}[where]
            n, info, ports, vict = C.full(M.pset(b), decap=d)
            names, Zc, Zg = C.transfer(n, info, ports, vict, F)
            L = LD.lines(mo, idig, ihost, m, rdir, b)
            dg = [l for l in L if l[0] == 'digital']; dh = [l for l in L if l[0] == 'd2h']
            row[b] = dict(dig={v: synth(dg, Zc, names.index(v)) for v in ('dig', 'core_bias', 'qvco')},
                          d2h={v: synth(dh, Zc, names.index(v)) for v in ('dig', 'core_bias', 'qvco')},
                          q_nC=dg[0][3]/2/78.125e6*1e9/np.sinc(78.125e6*{'opt': 1.5e-9, 'nom': 1.2e-9, 'pess': 0.8e-9}[b])**2)
        res[f'{where}|{c}'] = row
        print(f"{c:5.1f} | {where:6s} | " + ' | '.join(f"{row[b]['dig']['dig']:5.0f}/{row[b]['dig']['core_bias']:5.0f}/{row[b]['dig']['qvco']:5.0f}" for b in row)
              + ' || ' + ' | '.join(f"{row[b]['d2h']['dig']:5.0f}" for b in row))
print('charge per cycle (nC): ' + ', '.join(f"{b} {res['macro|0'][b]['q_nC']:.2f}" for b in ('opt', 'nom', 'pess')))
json.dump(res, open('out/e4_decap_req.json', 'w'), indent=0)
