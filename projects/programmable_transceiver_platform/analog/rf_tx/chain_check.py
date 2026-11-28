#!/usr/bin/env python3
"""RF-TX-POUT check on the board-matched chain bench (run_benches chain decks, txmix + txsum + rfdriver) for netlist views
    python3 chain_check.py <label>=<json {block: netlist under analog/rf_tx}> ...     -> generated/rf_tx-chain-check.json
Per view: the board match is designed from that view's own driver output admittance (zout deck, as run_benches), then
saturated constant-envelope (vin 1.0, sat) and linear (vin 0.3) at tt / 27 C / 3.3 V and ss / 32 C / 3.15 V."""
import json, os, sys
import numpy as np
from pathlib import Path
import simulate as S, run_benches as B
HERE = Path(__file__).resolve().parent
res = {}
for a in sys.argv[1:]:
    lab, alt = a.split('=', 1); os.environ['RFTX_VIEWFILES'] = alt
    zw = S.run_decks({'zout': S.zout_deck('ext', out='zout.txt')}, f'chz_{lab}'); zd = np.loadtxt(zw / 'zout.txt')
    m = S.design_match(complex(zd[1], zd[3]))
    cases = {'sat_tt': dict(vin_i=1.0, sat=1), 'lin_tt': dict(vin_i=0.3),
             'sat_ss_32C_3p15V': dict(vin_i=1.0, sat=1, corner='ss', temp=32, vdd=3.15), 'lin_ss_32C_3p15V': dict(vin_i=0.3, corner='ss', temp=32, vdd=3.15),
             'sat_ff_22C_3p35V': dict(vin_i=1.0, sat=1, corner='ff', temp=22, vdd=3.35),
             'sat_ss_32C_3p35V': dict(vin_i=1.0, sat=1, corner='ss', temp=32, vdd=3.35),
             'sat_ss_32C_3p50V': dict(vin_i=1.0, sat=1, corner='ss', temp=32, vdd=3.50),        # MANDATE 2 trim ceiling
             'lin_ff_22C_3p35V': dict(vin_i=0.3, corner='ff', temp=22, vdd=3.35)}
    only = [c for c in os.environ.get('CASES', '').split(',') if c]
    if only: cases = {k: v for k, v in cases.items() if k in only}
    decks = {k: S.chain_deck('ext', match=m, out=f'{k}.txt', **kw) for k, kw in cases.items()}
    w = S.run_decks(decks, f'chain_{lab}')
    res[lab] = {k: {kk: v for kk, v in S.chain_metrics(w, k, 8e-9).items() if kk in ('pad_dBm_50ohm', 'supply_mA')} for k in cases}
    print(lab, json.dumps({k: (v['pad_dBm_50ohm'], v['supply_mA'].get('rfdriver') if isinstance(v['supply_mA'], dict) else v['supply_mA']) for k, v in res[lab].items()}))
p = HERE / 'generated/rf_tx-chain-check.json'; old = json.load(open(p)) if p.exists() else {}; old.update(res)
open(p, 'w').write(json.dumps(old, indent=1) + '\n')
