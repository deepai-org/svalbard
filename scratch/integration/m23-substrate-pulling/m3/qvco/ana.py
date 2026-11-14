#!/usr/bin/env python3
"""QVCO r6b (RC-extracted, full-pessimistic tank PF85, band 11, VTUNE 2.1 V, 12 mA tail) injection / substrate sensitivities.
Same edge-time method as adler_bench/bench.py (validated against Adler to 0.5 %).
  q_base  : no perturbation (f0, amplitude; null control for the FM demodulation)
  q_dinj  : 100 uA differential current into the I tank at FINJ          -> f_L per mA (Adler: f0/(2Q) * Iinj/Iosc)
  q_subhf : 50 mV tone at FINJ on SUB (all NMOS bulks + all extracted wire caps to VSS + the spiral substrate legs)
  q_vddhf : 10 mV tone at FINJ on the core VDD
  q_subdc : +50 mV DC on SUB                                               -> quasi-static K_sub (MHz/V)
  q_vdd2f / q_sub2f : tones at F2 (near 2 f0) on VDD / SUB                 -> second-harmonic (tail / common-mode) pulling
The FM amplitude at the beat (|FINJ - f0| or |F2 - 2 f0|) is the one-sided lock range for that injection amplitude."""
import numpy as np, json, os
FINJ = 2467.0e6; TS = 30e-9
def edges(t, v):
    k = np.where((v[:-1] < 0) & (v[1:] >= 0))[0]; return t[k]-v[k]*(t[k+1]-t[k])/(v[k+1]-v[k])
def load(n):
    x = np.loadtxt(n+'.txt'); t = x[:, 0]; m = t > TS; return t[m], x[m, 1]
def f0amp(n):
    t, v = load(n); e = edges(t, v); return 1/np.polyfit(np.arange(len(e)), e, 1)[0], float(np.abs(v).max())
def fm(n, beat):
    t, v = load(n); e = edges(t, v); fi = 1/np.diff(e); tm = (e[1:]+e[:-1])/2
    A = np.array([np.ones_like(tm), tm-tm.mean(), np.sin(2*np.pi*beat*tm), np.cos(2*np.pi*beat*tm)]).T
    c, *_ = np.linalg.lstsq(A, fi, rcond=None); return float(np.hypot(c[2], c[3])), float((fi-A@c).std())
out = {}
f0, a0 = f0amp('q_base'); out['q_base'] = dict(f0_MHz=f0/1e6, amp_diff_pk_V=a0, null_fm_kHz_at_beat=fm('q_base', FINJ-f0)[0]/1e3)
for n, amp, unit, key in (('q_dinj', 0.1, 'mA', 'fL_kHz_per_mA'), ('q_subhf', 50, 'mV', 'fL_kHz_per_mV'), ('q_vddhf', 10, 'mV', 'fL_kHz_per_mV'),
                          ('q_vdd2f', 10, 'mV', 'fL_kHz_per_mV'), ('q_sub2f', 50, 'mV', 'fL_kHz_per_mV')):
    if not os.path.exists(n+'.txt'): continue
    f, a = f0amp(n); F = float(open(n+'.finj').read()) if os.path.exists(n+'.finj') else FINJ
    beat = abs(F-f) if F < 3.5e9 else abs(F-2*f)
    d, rs = fm(n, beat); out[n] = dict(f_MHz=f/1e6, beat_MHz=beat/1e6, fm_amp_kHz=d/1e3, resid_kHz_rms=rs/1e3, **{key: d/1e3/amp}, mean_shift_kHz=(f-f0)/1e3)
if os.path.exists('q_subdc.txt'):
    f, a = f0amp('q_subdc'); out['q_subdc'] = dict(f_MHz=f/1e6, K_sub_MHz_per_V=(f-f0)/1e6/0.05, amp=a)
if 'q_dinj' in out:
    # Adler cross-check: fL = f0/(2 Q) * Iinj / Iosc, Iosc = V/(Q w L)  ->  fL = Iinj * w L f0 /(2 V)   (Q cancels), L = 2.25 nH (l85 spiral)
    L = 2.2517e-9; pred = 0.1e-3*2*np.pi*f0*L*f0/(2*a0)
    out['q_dinj']['adler_pred_kHz'] = pred/1e3; out['q_dinj']['ratio_sim_to_adler'] = out['q_dinj']['fm_amp_kHz']*1e3/pred
print(json.dumps(out, indent=1)); json.dump(out, open('qvco_sens.json', 'w'), indent=1)
