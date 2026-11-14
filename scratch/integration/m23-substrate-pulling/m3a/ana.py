#!/usr/bin/env python3
"""M3a analysis: two-ring decks.  For each run: free frequencies of ring A / B (linear fit of rising-edge times), the beat
df = fB - fA, the phase-difference drift (lock test), and the pulling of each ring = amplitude of its instantaneous-frequency
modulation at k*df (k = 1,2,3,4,8), by least squares (const + slope + sin/cos per k).  For weak injection Adler gives a
frequency-modulation amplitude equal to the one-sided lock range f_L, independent of df (df >> f_L); the phase spur is
20log10(f_L / (2 k df)) dBc and the peak time error f_L/(2 pi k df f0).
usage: ana.py name [t_settle_ns]"""
import sys, json, numpy as np
def edges(t, v):
    th = (v.max()+v.min())/2; k = np.where((v[:-1] < th) & (v[1:] >= th))[0]
    return t[k]+(th-v[k])*(t[k+1]-t[k])/(v[k+1]-v[k])
def ring(e, df, ks=(1, 2, 3, 4, 8)):
    n = np.arange(len(e)); p = np.polyfit(n, e, 1); f0 = 1/p[0]
    fi = 1/np.diff(e); tm = (e[1:]+e[:-1])/2
    x = (tm-tm.mean())/np.ptp(tm); cols = [np.ones_like(tm), tm-tm.mean(), x**2, x**3]      # const + drift (bias settling: up to cubic)
    for k in ks: cols += [np.sin(2*np.pi*k*df*tm), np.cos(2*np.pi*k*df*tm)]
    A = np.array(cols).T; c, *_ = np.linalg.lstsq(A, fi, rcond=None)
    amp = {k: float(np.hypot(c[4+2*i], c[5+2*i])) for i, k in enumerate(ks)}
    res = fi-A@c
    return f0, amp, float(res.std()), float(c[1])
def run(name, ts=60e-9):
    d = np.loadtxt(name+'.txt'); t = d[:, 0]; m = t > ts
    ea, eb = edges(t[m], d[m, 1]), edges(t[m], d[m, 2])
    fa = 1/np.polyfit(np.arange(len(ea)), ea, 1)[0]; fb = 1/np.polyfit(np.arange(len(eb)), eb, 1)[0]
    df = fb-fa
    # phase difference (cycles) of B relative to A sampled at A edges
    ok = (ea > eb[0]) & (ea < eb[-1]); phb = np.interp(ea[ok], eb, np.arange(len(eb))); dphi = phb-np.arange(len(ea))[ok]; dphi -= dphi[0]
    half = len(dphi)//2
    out = dict(name=name, window_ns=[ts*1e9, float(t[-1]*1e9)], fA_MHz=fa/1e6, fB_MHz=fb/1e6, df_MHz=df/1e6, df_pct=100*df/fa,
               dphi_total_cycles=float(dphi[-1]), dphi_last_half_span_cycles=float(np.ptp(dphi[half:])),
               locked=bool(np.ptp(dphi[half:]) < 0.1 and abs(dphi[-1]) < 1.5),
               vT_mean=float(d[m, 3].mean()), vT_ripple_mVpp=float(np.ptp(d[m, 3])*1e3), vC_ripple_mVpp=float(np.ptp(d[m, 4])*1e3))
    if abs(df) > 1.2/(t[-1]-ts):
        for tag, e in (('A', ea), ('B', eb)):
            f0, amp, rs, slope = ring(e, abs(df))
            out[f'pull_{tag}_kHz_at_k'] = {k: round(v/1e3, 2) for k, v in amp.items()}
            out[f'resid_{tag}_kHz_rms'] = rs/1e3; out[f'drift_{tag}_MHz_per_us'] = slope/1e12
    return out
if __name__ == '__main__':
    r = run(sys.argv[1], float(sys.argv[2])*1e-9 if len(sys.argv) > 2 else 60e-9)
    print(json.dumps(r, indent=1))
    try: allr = json.load(open('m3a_results.json'))
    except Exception: allr = {}
    allr[sys.argv[1]] = r; json.dump(allr, open('m3a_results.json', 'w'), indent=1)
