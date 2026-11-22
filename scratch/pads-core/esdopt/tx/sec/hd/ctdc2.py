"""ctdc.py <model> <tag>: pad DC current vs pad voltage 3.0..4.6 V, termination off, driver off, DVDD = VDD (ring powered), tt / ss / ff at 32 C,
VDD 3.15 / 3.3 / 3.45: what the pad draws if a board centre tap holds it above VDD (wired TX WT53 option 1b, CT 4.5 V)."""
import sys, json
sys.path.insert(0, '/home/ubuntu/svalbard/scratch/pads-core/esdopt/tx')
import numpy as np, tb2
text, cell, ports = tb2.load(sys.argv[1]); W = tb2.HERE / 'bench' / sys.argv[2]; out = {}
for pr, t, vdd in [('ss', 85, 3.15), ('ff', 85, 3.15), ('ss', 85, 3.0), ('typical', 125, 3.15)]:
    over = {'TERM_ENABLE': 'VTERM_ENABLE TERM_ENABLE 0 0\n', 'TERM_VCM': 'VTERM_VCM TERM_VCM 0 1.65\n'}
    for k in range(4): over[f'TERM_TRIM{k}'] = f'VT{k} TERM_TRIM{k} 0 0\n'
    d = tb2.header(pr, t) + text + tb2.controls(ports, vdd, over) + 'Xpad ' + ' '.join(ports) + f' {cell}\nVPA PAD_P 0 3.3\nVNA PAD_N 0 3.3\n'
    name = f'ct_{pr}_{t}'; d += tb2.s.control(W, name, 'dc VPA 3.3 4.0 0.05', 'i(VPA)')
    x = np.atleast_2d(tb2.s.run(W, name, d, timeout_s=3000))
    out[f'{pr}_{t}_{vdd}'] = {f'{v:.2f}': round(-float(i) * 1e3, 4) for v, i in zip(x[:, 0], x[:, 1])}
    print(pr, t, vdd, {k: v for k, v in out[f'{pr}_{t}_{vdd}'].items() if k in ('3.5', '3.6', '3.6', '3.7', '3.8')}, flush=True)
    for q in list(W.glob('*.dat')) + list(W.glob('*.spice')): q.unlink()
(tb2.HERE / 'bench' / f'{sys.argv[2]}-ctdc.json').write_text(json.dumps(dict(model=sys.argv[1], mA=out), indent=1))
