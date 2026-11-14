#!/usr/bin/env python3
"""Cross-ripple between the two outputs of the extracted pt_pll_vreg2 (the 'estimated -30 dB' of PD36): amplitude of the supply of
ring A (VT) and ring B (VC) at the lines that belong to only one ring (f, 8f), by least squares over the settled window.
isolation = 20log10(|VT at fB| / |VC at fB|) and the reverse."""
import sys, json, numpy as np
import ana
def amp(t, v, fs):
    cols = [np.ones_like(t), t-t.mean()]
    for f in fs: cols += [np.sin(2*np.pi*f*t), np.cos(2*np.pi*f*t)]
    A = np.array(cols).T; c, *_ = np.linalg.lstsq(A, v, rcond=None)
    return [float(np.hypot(c[2+2*i], c[3+2*i])) for i in range(len(fs))]
out = {}
for n in sys.argv[1:]:
    d = np.loadtxt(n+'.txt'); t = d[:, 0]; m = t > 60e-9; t = t[m]
    ea, eb = ana.edges(t, d[m, 1]), ana.edges(t, d[m, 2])
    fa = 1/np.polyfit(np.arange(len(ea)), ea, 1)[0]; fb = 1/np.polyfit(np.arange(len(eb)), eb, 1)[0]
    fs = [fa, fb, 8*fa, 8*fb]
    vt = amp(t, d[m, 3], fs); vc = amp(t, d[m, 4], fs)
    r = dict(fA_MHz=fa/1e6, fB_MHz=fb/1e6,
             VT_mV=dict(at_fA=vt[0]*1e3, at_fB=vt[1]*1e3, at_8fA=vt[2]*1e3, at_8fB=vt[3]*1e3),
             VC_mV=dict(at_fA=vc[0]*1e3, at_fB=vc[1]*1e3, at_8fA=vc[2]*1e3, at_8fB=vc[3]*1e3),
             iso_B_to_A_dB=dict(f=20*np.log10(vt[1]/vc[1]), f8=20*np.log10(vt[3]/vc[3])),
             iso_A_to_B_dB=dict(f=20*np.log10(vc[0]/vt[0]), f8=20*np.log10(vc[2]/vt[2])))
    out[n] = r; print(n, json.dumps(r, default=float))
json.dump(out, open('xrip.json', 'w'), indent=1, default=float)
