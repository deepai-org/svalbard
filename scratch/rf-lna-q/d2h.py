"""D2H pickup at 2421.875 MHz into RF_RX for D2H settings (coordinator ruling 4). Anchor: pt_rf PDN model e9 (scratch/integration/m1-pdn/out/rf,
RXa|lna nominal source = 1.0 ns edge, half periodic content, div2 78.125 MHz: 2206.6 uV rms on die VSS). Line amplitude scales as in
loads.py: payload content x sinc^2(f tr) x host current (div4 halves the edge rate). Bounce -> input: LNA metal-aware view on the pt_rf
package model, min / nom / max bound (close_rext/bounce_rf.json). Input-referred power with the e9 convention (V^2 / 50 ohm)."""
import json, math, numpy as np
F = 2.421875e9; V_NOM = 2206.6e-6
conv = {b['model']: b['bounce_to_input_referred_db'] for b in json.load(open('/home/ubuntu/svalbard/scratch/rf_rx/close_rext/bounce_rf.json')) if b['die_decap']}
edge = lambda tr: min(1.0, 1.0 / (math.pi * F * tr) ** 2)   # envelope of sinc^2 (no credit for the sinc nulls; loads.py env)
S = {'fast 0.76 ns, periodic in phase, div2': (1.0, 0.76e-9, 1.0), 'nominal 1.0 ns, half periodic, div2 (anchor)': (0.5, 1.0e-9, 1.0),
     'slow 1.4 ns, PRBS payload, div2': (0.163, 1.4e-9, 1.0), 'slow 1.4 ns, PRBS payload, div4': (0.163, 1.4e-9, 0.5),
     'nominal 1.0 ns, half periodic, div4': (0.5, 1.0e-9, 0.5)}
out = {}
for k, (c, tr, r) in S.items():
    v = V_NOM * (c / 0.5) * (edge(tr) / edge(1.0e-9)) * r
    out[k] = dict(vss_uV_rms=round(v * 1e6, 2), **{f'input_dBm_{m}': round(10 * math.log10((v * 10 ** (conv[m] / 20)) ** 2 / 50 * 1e3), 1) for m in ('RF_min', 'RF_nom', 'RF_max')})
    print(k, out[k])
json.dump(dict(limit_dBm=-100.0, conversion_db=conv, rows=out, fallback='2421.875 MHz kept out of the channel plan (31st harmonic of 78.125 / 62nd of 39.0625 MHz)'),
          open('/home/ubuntu/svalbard/scratch/rf_rx/d2h/d2h_pickup.json', 'w'), indent=1)
