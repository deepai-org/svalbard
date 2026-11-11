"""Equivalence: the published readiness deck (txpad + interlock + compensated buffer, tran 300 ns) with the
canonical vs the compact-array buffer extraction, tt27 / ss22 / ff32."""
import sys, json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads')
import stress_safe_clamp as s
G = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads/generated/termination-buffer-candidate/source-headroom/reference-reset')
W = Path(__file__).resolve().parent
lines = (G / 'connected.spice').read_text().splitlines()
a = next(i for i, l in enumerate(lines) if l.startswith('.subckt buffer_compensated_flat'))
b = next(i for i in range(a, len(lines)) if lines[i].startswith('.ends'))
new = Path('/home/ubuntu/svalbard/scratch/pads-pd28/tbuf/comp/physical.spice').read_text().splitlines()
na = next(i for i, l in enumerate(new) if l.startswith('.subckt buffer_compensated_flat'))
nb = next(i for i in range(na, len(new)) if new[i].startswith('.ends'))
decks = {'old': lines, 'new': lines[:a] + new[na:nb + 1] + lines[b + 1:]}
def job(arg):
    v, (p, t) = arg
    text = '\n'.join(decks[v]) + '\n'
    text = text.replace('.temp 27\n', '.temp 27\n') if '.temp' in text else text.replace('.lib ', f'.temp {t}\n.lib ', 1)
    text = s.corner(text, p, t)
    name = f'{v}_{p}_{t}'
    text = text.replace('/home/ubuntu/svalbard/scratch/pad-tx-restore-reference-readiness/connected.dat', str(W / f'{name}.dat'))
    (W / f'{name}.spice').write_text(text)
    x = s.run(W, name, text, timeout_s=7200)
    return name, x
cases = [(v, c) for c in (('typical', 27), ('ss', 22), ('ff', 32)) for v in ('old', 'new')]
with ThreadPoolExecutor(4) as ex:
    res = dict(ex.map(job, cases))
out = {}
for p, t in (('typical', 27), ('ss', 22), ('ff', 32)):
    o, n = res[f'old_{p}_{t}'], res[f'new_{p}_{t}']
    tt = np.linspace(0, min(o[-1, 0], n[-1, 0]), 3001)
    vo, vn = np.interp(tt, o[:, 0], o[:, 1]), np.interp(tt, n[:, 0], n[:, 1])
    io, inn = np.interp(tt, o[:, 0], o[:, 6]), np.interp(tt, n[:, 0], n[:, 6])
    def ready(x):
        k = np.where(x[:, 8] > 1.65)[0]; return float(x[k[0], 0] * 1e9) if len(k) else None
    out[f'{p}_{t}'] = dict(term_vcm_final_old=float(vo[-1]), term_vcm_final_new=float(vn[-1]),
                          term_vcm_max_abs_diff_mV=float(np.abs(vo - vn).max() * 1e3),
                          term_vcm_diff_last100ns_mV=float(np.abs(vo - vn)[tt > tt[-1] - 100e-9].max() * 1e3),
                          supply_mean_mA_old=float(-io[tt > tt[-1] - 100e-9].mean() * 1e3), supply_mean_mA_new=float(-inn[tt > tt[-1] - 100e-9].mean() * 1e3),
                          measured_ready_ns_old=ready(o), measured_ready_ns_new=ready(n))
    print(p, t, out[f'{p}_{t}'], flush=True)
(W / 'equivalence.json').write_text(json.dumps(out, indent=1))
