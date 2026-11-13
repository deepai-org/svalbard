#!/usr/bin/env python3
"""Tabulate bias-chain audit results: per-trunk output current ratio vs the fault-free baseline."""
import json, subprocess, sys
from pathlib import Path
W = Path(__file__).resolve().parent
subprocess.run([sys.executable, str(W / 'collect.py'), 'bias'], capture_output=True)
r = json.load(open(W / 'bias' / 'results.json'))
G = {'rf': ['lna', 'rxmix_i', 'rxmix_q', 'bbfilter_i', 'bbfilter_q', 'txmix_i', 'txmix_q', 'rfdriver'],
     'conv': ['adc_i', 'adc_q', 'dac_i', 'dac_q', 'refbuf'], 'pll': ['pll_ring_tx', 'pll_ring_rx', 'pll_ring_host'],
     'wire': ['ctle', 'detect', 'wiredtx'], 'debug': ['bb_tap_i', 'bb_tap_q', 'bb_tap_wmon']}
def row(k):
    v = r[k]
    if 'v_vbg' not in v:
        return f'{k}: no result (aborted={v.get("_aborted")})'
    s = [k.ljust(34)]
    for g, names in G.items():
        cur = [v.get('i_bias_' + n, float('nan')) * 1e6 for n in names]
        s.append(f'{g} {min(cur):6.2f}..{max(cur):6.2f}')
    s.append(f"lna {v.get('i_bias_lna', 0)*1e6:7.2f} uA | vbg {v['v_vbg']:.4f} root {v['v_root_ref']:.3f} vref0 {v['v_vref0']:.3f} "
             f"vcm {v['v_vcm']:.3f} trk_rf {v['v_trk_rf']:.3f} | ivdd {-v['ivdd_end']*1e6:7.1f} uA pk {-v['ivdd_pk']*1e3:6.2f} mA vbg_pk {v['vbg_pk']:.2f} pp {v['vbg_pp']:.1e}")
    return '  '.join(s)
for k in sorted(r):
    print(row(k))
