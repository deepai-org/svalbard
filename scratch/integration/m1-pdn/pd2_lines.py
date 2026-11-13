#!/usr/bin/env python3
"""PD2: per-line ripple spectrum at a victim tap (differential rail, and VSS vs board ground), opt/nom/pess.
pess = pessimistic source x worst of the three network sets per line (as e3). Used for the PSRR demand rows and the
QVCO regulator mask. Usage: pd2_lines.py <victim> <mode> [plan] ; importable: spectrum(victim, mode, decap, **build_kw)."""
import sys, json, numpy as np
import model as M, core as C, loads as LD

def spectrum(victims, mode, decap, level='evid+', sets=('opt', 'nom', 'pess'), psets=None, **kw):
    out, idig, ihost, m, rdir = LD.dc_loads(mode, level)
    L = {b: LD.lines(mode, idig, ihost, m, rdir, b) for b in ('pess', 'nom', 'opt')}
    F = np.array(sorted({l[2] for l in L['pess']}))
    Zc = {}; Zg = {}
    for s in sets:
        p = (psets or {}).get(s) or M.pset(s)
        n, info, ports, vict = C.full(p, decap=decap, **kw)
        names, Zc[s], Zg[s] = C.transfer(n, info, ports, vict, F)
    res = {}
    for v in victims:
        vi = names.index(v); rows = {}
        for b in ('opt', 'nom', 'pess'):
            pick = max if b == 'pess' else min if b == 'opt' else (lambda it: list(it)[len(sets)//2])
            for (ag, port, f, a, ae) in L[b]:
                k = int(np.searchsorted(F, f)); pi = C.PORTS.index(port)
                zd = pick(abs(Zc[s][k, vi, pi]) for s in sets); zg = pick(abs(Zg[s][k, vi, pi]) for s in sets)
                r = rows.setdefault((ag, f), {})
                r[b] = (a*zd, ae*zg)
        res[v] = rows
    return res

if __name__ == '__main__':
    v = sys.argv[1]; mode = sys.argv[2]; plan = sys.argv[3] if len(sys.argv) > 3 else '3nF_spread'
    d = {'none': C.decap_plan('none'), '3nF_spread': C.decap_plan('uniform', 3.0), '8nF_macro': C.decap_plan('digital', 8.0)}[plan]
    r = spectrum([v], mode, d)[v]
    print(f'{v} {mode} {plan}: aggressor, f MHz, rail ripple mV peak opt/nom/pess, VSS-vs-board uV peak (envelope) opt/nom/pess')
    for (ag, f), x in sorted(r.items(), key=lambda kv: -kv[1]['pess'][0])[:25]:
        print(f"  {ag:10s} {f/1e6:9.3f}  {x['opt'][0]*1e3:8.3f} / {x['nom'][0]*1e3:8.3f} / {x['pess'][0]*1e3:8.3f}    {x['opt'][1]*1e6:9.1f} / {x['nom'][1]*1e6:9.1f} / {x['pess'][1]*1e6:9.1f}")
