"""Termination-buffer readiness at the narrow-envelope corners, with nothing toggling: the published readiness deck
(extracted txpad + interlock + compensated buffer) with VDD held, reset released at 20 ns, TX qualified from 22 ns,
buffer request + termination + MAIN on from 78 ns and held, POST/DETECT/TMDS off; tran to 2 us.
Ready = |TERM_VCM - BUF_REF| <= 16.5 mV from then on (readiness-screen window). Usage: settle.py <old|new|tag=path> ..."""
import sys, json, re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
sys.path.insert(0, '/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads')
import stress_safe_clamp as s
G = Path('/home/ubuntu/svalbard/projects/programmable_transceiver_platform/analog/pads/generated/termination-buffer-candidate/source-headroom/reference-reset')
W = Path(__file__).resolve().parent
base = (G / 'connected.spice').read_text().splitlines()
def with_buffer(path):
    if path is None:
        return base
    new = Path(path).read_text().splitlines()
    a = next(i for i, l in enumerate(base) if l.startswith('.subckt buffer_compensated_flat'))
    b = next(i for i in range(a, len(base)) if base[i].startswith('.ends'))
    na = next(i for i, l in enumerate(new) if l.startswith('.subckt buffer_compensated_flat'))
    nb = next(i for i in range(na, len(new)) if new[i].startswith('.ends'))
    return base[:a] + new[na:nb + 1] + base[b + 1:]
SRC = {'old': None, 'new': '/home/ubuntu/svalbard/scratch/pads-pd28/tbuf/comp/physical.spice'}
for a in sys.argv[1:]:
    if '=' in a:
        k, v = a.split('='); SRC[k] = v
TAGS = [a.split('=')[0] for a in sys.argv[1:]] or ['old', 'new']
ON = lambda t0: f'PWL(0n 0 {t0}n 0 {t0+0.02}n 3.3 3000n 3.3)'
def deck(tag, vdd):
    out = []
    for l in with_buffer(SRC[tag]):
        f = l.split(' ', 1)[0]
        if f == 'VDD': l = f'VDD VDD 0 PWL(0n 0 10n {vdd} 3000n {vdd})'
        elif f == 'VTX_RESET': l = 'VTX_RESET TX_RESET 0 PWL(0n 0 1n 0 1.02n 3.3 20n 3.3 20.02n 0 3000n 0)'
        elif f == 'VTX_QUALIFIED': l = 'VTX_QUALIFIED TX_QUALIFIED 0 ' + ON(22)
        elif f == 'VBUF_REQUEST': l = 'VBUF_REQUEST BUF_REQUEST VSS ' + ON(78)
        elif f == 'VTERM_ENABLE': l = 'VTERM_ENABLE REQ_TERM_ENABLE 0 ' + ON(78)
        elif f == 'VEN_MAIN': l = 'VEN_MAIN REQ_EN_MAIN 0 PWL(0n 0 78n 0 78.02n 1 3000n 1)'
        elif f in ('VEN_POST', 'VEN_DETECT', 'VEN_TMDS'): l = f'{f} ' + l.split()[1] + ' 0 0'
        elif f == 'VTRAFFIC_READY': l = 'VTRAFFIC_READY TRAFFIC_READY 0 0'
        elif l.startswith('tran '): l = 'tran 20p 2000n'
        elif l.startswith('wrdata '): l = 'wrdata OUT v(TERM_VCM) v(BUF_REF) v(BUF_ENABLE) v(TERM_ENABLE) v(MEASURED_READY)'
        out.append(l)
    return '\n'.join(out) + '\n'
import os
CORNERS = [('typical', 27, 3.3), ('ss', 22, 3.15), ('ss', 32, 3.15), ('ff', 22, 3.35), ('ff', 32, 3.35)]
if os.environ.get('SETTLE_CORNERS') == 'det':
    CORNERS = [('ss', 22, 3.15), ('typical', 27, 3.3)]
def job(arg):
    tag, (p, t, v) = arg
    name = f'{tag}_{p}_{t}_{v}' + ('_det' if os.environ.get('SETTLE_CORNERS') == 'det' else '')
    d = s.corner(deck(tag, v), p, t).replace('wrdata OUT', f'wrdata {W}/{name}.dat')
    x = s.run(W, name, d, timeout_s=14400)
    tt, vcm, ref = x[:, 0], x[:, 1], x[:, 2]
    err = np.abs(vcm - ref); m = tt >= 78e-9
    bad = np.where(m & (err > 0.0165))[0]
    ready = float((tt[bad[-1]] - 78e-9) * 1e9) if len(bad) and bad[-1] < len(tt) - 1 else None
    mr = x[:, 5] > 1.65
    ups = np.where(mr[1:] & ~mr[:-1])[0]; downs = np.where(~mr[1:] & mr[:-1])[0]
    det = dict(detector_first_assert_ns=float((tt[ups[0]] - 78e-9) * 1e9) if len(ups) else None,
               detector_asserts=int(len(ups)), detector_deasserts_after_first=int(sum(d > ups[0] for d in downs)) if len(ups) else 0,
               detector_asserted_while_outside_window_ns=float(((mr & (err > 0.0165)).sum()) * 0) if False else float(np.trapezoid((mr & (err > .0165)).astype(float), tt) * 1e9))
    return name, dict(**det, ready_after_enable_ns=ready, settled_at_end=bool(err[-1] <= 0.0165), final_err_mV=float(err[-1] * 1e3),
                      peak_vcm_v=float(vcm[m].max()), min_vcm_after_100ns_v=float(vcm[tt > 100e-9].min()), ref_v=float(ref[-1]))
with ThreadPoolExecutor(2) as ex:
    res = dict(ex.map(job, [(g, c) for c in CORNERS for g in TAGS]))
for k, v in res.items(): print(k, v, flush=True)
(W / ('settle-' + '-'.join(TAGS) + ('-det' if os.environ.get('SETTLE_CORNERS') == 'det' else '') + '.json')).write_text(json.dumps(res, indent=1))
