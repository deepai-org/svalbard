#!/usr/bin/env python3
"""rfdriver / rf_tx power rework check (2026-11-28): driver benches and in-block supply IR for several netlist views.

    python3 power_check.py <label>=<rfdriver netlist under analog/rf_tx or 'ext'> ... [--droop mV]

For each view: the run_benches driver decks (pad power / voltage gain vs input amplitude and gain code, mute, bypass,
off) and an in-block IR bench: tt / 27 C / 3.3 V, code 15, 0.3 V input, driver loaded as in the driver deck. The worst
in-block drop is max(V(VDD pin) - V(VDD.*)) and max(V(VSS.*) - V(VSS pin)) over the resisted supply nodes (R+C views
only), time-averaged over the last 8 LO cycles. --droop subtracts an extra top-level droop from the supply.
Writes generated/rfdriver-power-check.json."""
import json, os, sys, re
import numpy as np
from pathlib import Path
import simulate as S
import run_benches as B

HERE = Path(__file__).resolve().parent


def ir_deck(view, nodes, vdd=3.3, out='ir.txt'):
    d = B.driver_deck(view, amp=0.3, gain=15, out=out, vdd=vdd)
    probes = ' '.join(f'v(x1.{n})' for n in nodes)
    return d.replace(f'wrdata {out} v(lp)-v(ln)', f'wrdata {out} v(vdd) v(VSS) {probes}\n* ').replace('tran 1p 5n 0 2p', 'tran 2p 5n 0 4p')


def supply_nodes(path):
    txt = open(path).read()
    ns = sorted(set(re.findall(r'\b((?:VDD|VSS)\.[tn]\d+)\b', txt)))
    return ns


def main(args):
    droop = 0.0
    if '--droop' in args:
        i = args.index('--droop'); droop = float(args[i + 1]) / 1e3; args = args[:i] + args[i + 2:]
    out = {}
    for a in args:
        lab, f = a.split('=')
        os.environ['RFTX_VIEWFILES'] = json.dumps({} if f == 'ext' else {'rfdriver': f})
        decks, meta = {}, {}
        quick = os.environ.get('QUICK') == '1'
        for amp in ((0.3,) if quick else (0.05, 0.15, 0.3, 0.6)):
            decks[f'drv_a{int(amp * 1000)}'] = B.driver_deck('ext', amp=amp, vdd=3.3 - droop, out=f'drv_a{int(amp * 1000)}.txt'); meta[f'drv_a{int(amp * 1000)}'] = amp
        for code in (() if quick else (0, 7, 15)):
            decks[f'drv_code{code}'] = B.driver_deck('ext', amp=0.3, gain=code, vdd=3.3 - droop, out=f'drv_code{code}.txt'); meta[f'drv_code{code}'] = 0.3
        nodes = supply_nodes(HERE / f) if f != 'ext' else []
        if nodes and not quick: decks['ir'] = ir_deck('ext', nodes, vdd=3.3 - droop)
        work = S.run_decks(decks, f'power_{lab}')
        r = {k: B.driver_metrics(work, k, meta[k]) for k in meta}
        if nodes and not quick:
            y = np.loadtxt(work / 'ir.txt'); t = y[:, 0]; m = t >= 5e-9 - 8 * S.T_LO
            cols = y[:, 1::2]                      # wrdata: t, v pairs
            vd, vs = cols[m, 0].mean(), cols[m, 1].mean(); vn = cols[m, 2:].mean(axis=0)
            dv = {n: (vd - v if n.startswith('VDD') else v - vs) for n, v in zip(nodes, vn)}
            wv = max((k for k in dv if k.startswith('VDD')), key=lambda k: dv[k]); ws = max((k for k in dv if k.startswith('VSS')), key=lambda k: dv[k])
            r['ir_mV'] = dict(VDD_worst=round(1e3 * dv[wv], 2), VDD_node=wv, VSS_worst=round(1e3 * dv[ws], 2), VSS_node=ws,
                              nodes=len(nodes), method='driver deck code 15 / 0.3 V, mean of last 8 LO cycles, Magic extresist (tol 0.001) + fixcap16 C repair')
        out[lab] = dict(netlist=f, droop_mV=round(droop * 1e3, 1), results=r)
        print(lab, json.dumps({k: (v.get('pad_dBm_50ohm'), v.get('voltage_gain'), v.get('supply_mA')) if isinstance(v, dict) and 'pad_dBm_50ohm' in v else v for k, v in r.items()}))
    p = HERE / 'generated/rfdriver-power-check.json'
    old = json.load(open(p)) if p.exists() else {}
    old.update(out); open(p, 'w').write(json.dumps(old, indent=1) + '\n')


if __name__ == '__main__':
    main(sys.argv[1:])
