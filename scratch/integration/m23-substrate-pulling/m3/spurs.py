#!/usr/bin/env python3
"""M3d: spur table for every supported clock / rate.
(1) RF band hits: harmonics n*f inside 2400..2483.5 MHz (+-10 MHz guard = half a 20 MHz channel).
(2) Baseband hits: n*f (n <= 12) that alias into 0..10 MHz at the converter rate fs when the source is NOT derived from the
    converter clock (asynchronous) - the analog path is substrate/supply coupling into the ADC input / bbfilter (M2).
Level estimate (in-band): the A5 shared-ground model, reused unchanged for comparability: I_n = 2 Q f0 env(f tw) env(f tr),
V_cm = I_n * Z_grid (0.1 .. 0.5 ohm), LNA CMRR 30 .. 25 dB, into 50 ohm.  Spec (A5 proposal): <= -100 dBm on a used channel."""
import numpy as np, json
BAND = (2400.0, 2483.5); GUARD = 10.0
env = lambda x: min(1.0, 1/(np.pi*x))
def level(f0, n, q, tr, tw=None):
    f = n*f0*1e6; tw = tw or tr; In = 2*q*f0*1e6*env(f*tw)*env(f*tr)
    r = []
    for zg, cmrr in ((0.1, 30), (0.5, 25)):
        vd = In*zg*10**(-cmrr/20); r.append(10*np.log10(max(vd**2/2/50/1e-3, 1e-30)))
    return In, r
# name: (f0 MHz, charge per cycle C, edge s, pulse width s or None, mode in which it runs, note)
S = {
 'macro core 78.125 (host 156.25/2)':            (78.125, 0.35e-9, 0.15e-9, 1.6e-9, 'RF', 'A5 charge'),
 'macro core 62.5 (host 125/2, GX-5)':           (62.5, 0.35e-9, 0.15e-9, 1.6e-9, 'RF', 'A5 charge'),
 'H2D clock pad 156.25':                         (156.25, 0.03e-9, 0.3e-9, None, 'RF', 'rx pad + tree, est'),
 'H2D clock pad 125':                            (125.0, 0.03e-9, 0.3e-9, None, 'RF', 'est'),
 'H2D data 312.5 Mword/s':                       (312.5, 0.03e-9, 0.3e-9, None, 'RF', 'est'),
 'D2H 78.125 DDR (host-follow), slow slew':      (78.125, 0.165e-9, 3e-9, 6.4e-9, 'RF', 'A5 charge'),
 'D2H 78.125 DDR (host-follow), FAST slew':      (78.125, 0.165e-9, 1e-9, 6.4e-9, 'RF', 'PDN-01 says slow slew in RF modes; this is the mis-set case'),
 'host_follow ring 625 (pll_cdr N=4)':           (625.0, 9.6e-12, 0.1e-9, None, 'RF', '6 mA avg; behind pt_pll_vreg2 unless BYP'),
 'host_follow ring 500 (125 MHz host)':          (500.0, 12e-12, 0.1e-9, None, 'RF', '6 mA avg'),
 'conv clock 39.0625 (ring/16)':                 (39.0625, 0.02e-9, 0.2e-9, None, 'RF', 'A5 charge'),
 'conv clock 78.125 (ring/8, 80 MS/s class)':    (78.125, 0.02e-9, 0.2e-9, None, 'RF', 'A5 charge'),
 'conv clock 40 (int/ref/aux)':                  (40.0, 0.02e-9, 0.2e-9, None, 'RF', 'A5 charge'),
 'conv clock 80 (int/ref/aux)':                  (80.0, 0.02e-9, 0.2e-9, None, 'RF', 'A5 charge'),
 'conv per-core 20':                             (20.0, 0.01e-9, 0.2e-9, None, 'RF', 'A5 charge'),
 'LO reference 50 (REF_IN, lo_pfdcp)':           (50.0, 0.005e-9, 0.3e-9, None, 'RF', 'PFD/CP + ref buffer'),
 'aosc 47.7 (40..60)':                           (47.7, 0.004e-9, 0.3e-9, None, 'RF(off by rule SUB-04)', 'A5 charge'),
 'ring 480 (USB HS / 1.92G)':                    (480.0, 12.5e-12, 0.1e-9, None, 'wired', '6 mA'),
 'ring 625 (2.5G, 1.25G)':                       (625.0, 9.6e-12, 0.1e-9, None, 'wired', ''),
 'ring 750 (1.5G)':                              (750.0, 9e-12, 0.1e-9, None, 'wired', ''),
 'ring 810 (1.62G / 3.24G)':                     (810.0, 9.7e-12, 0.1e-9, None, 'wired', 'BYP mode'),
 'ring 742.5 (1.485G SDI)':                      (742.5, 9e-12, 0.1e-9, None, 'wired', ''),
 'ring 741.758 (1.485/1.001G)':                  (742.5/1.001, 9e-12, 0.1e-9, None, 'wired', ''),
 'wrx_cap 625 (capture)':                        (625.0, 30e-12, 0.1e-9, None, 'wired', '~19 mA switching est'),
 'wrx_cap 810 (capture)':                        (810.0, 30e-12, 0.1e-9, None, 'wired', ''),
}
rows = []
for name, (f0, q, tr, tw, mode, note) in S.items():
    for n in range(int(np.ceil((BAND[0]-GUARD)/f0)), int(np.floor((BAND[1]+GUARD)/f0))+1):
        In, (lo, hi) = level(f0, n, q, tr, tw)
        f = n*f0; inband = BAND[0] <= f <= BAND[1]
        rows.append(dict(source=name, mode=mode, n=n, f_MHz=round(f, 4), in_band=bool(inband), I_uA=round(In*1e6, 3),
                         dBm_best=round(lo, 1), dBm_worst=round(hi, 1), margin_to_m100_worst_dB=round(-100-hi, 1), note=note))
rows.sort(key=lambda r: r['f_MHz'])
# carrier-derived D2H: LO/32 clock, LO/16 words -> harmonic 32 (16) sits exactly on the LO for every channel
cd = []
for flo in (2402.0, 2441.0, 2480.0):
    f0 = flo/32; In, (lo, hi) = level(f0, 32, 0.165e-9, 3e-9, 6.4e-9); In2, (lo2, hi2) = level(f0, 32, 0.165e-9, 1e-9, 6.4e-9)
    cd.append(dict(f_lo=flo, d2h_clock_MHz=round(f0, 4), harmonic=32, lands_on='LO exactly (DC after the mixer; data-dependent amplitude -> noise around DC)',
                   dBm_slow_slew=[round(lo, 1), round(hi, 1)], dBm_fast_slew=[round(lo2, 1), round(hi2, 1)]))
# baseband aliases
FS = {'39.0625 (host-follow/16)': 39.0625, '78.125 (host-follow/8)': 78.125, '40 (int/ref/aux)': 40.0, '80 (int/ref/aux)': 80.0}
COH = {'39.0625 (host-follow/16)': (78.125, 156.25, 312.5, 625.0, 39.0625), '78.125 (host-follow/8)': (78.125, 156.25, 312.5, 625.0), '40 (int/ref/aux)': (40.0, 80.0, 20.0), '80 (int/ref/aux)': (40.0, 80.0, 20.0)}
bb = []
for name, (f0, q, tr, tw, mode, note) in S.items():
    for fsn, fs in FS.items():
        coherent = any(abs(f0/c-round(f0/c)) < 1e-9 or abs(c/f0-round(c/f0)) < 1e-9 for c in COH[fsn]) and not name.startswith(('conv clock 40', 'conv clock 80', 'LO ref', 'aosc', 'ring', 'wrx', 'macro core 62.5', 'H2D clock pad 125', 'host_follow ring 500')) or abs(f0-fs) < 1e-9
        for n in range(1, 13):
            f = n*f0; a = abs(f-round(f/fs)*fs)
            if a <= 10.0 and not (coherent and a < 1e-6):
                if a < 1e-6 and f0 in (fs, fs/2): continue
                bb.append(dict(source=name, mode=mode, fs=fsn, n=n, f_MHz=round(f, 4), alias_MHz=round(a, 4)))
out = dict(band=BAND, guard=GUARD, rf_rows=rows, carrier_derived_d2h=cd, baseband_alias_rows=bb)
json.dump(out, open('spurs.json', 'w'), indent=1)
print('RF-band hits (in band or within 10 MHz):')
for r in rows: print(f"  {r['f_MHz']:9.3f} {'IN ' if r['in_band'] else 'edge'} n={r['n']:3d} {r['source']:44s} {r['mode']:8s} {r['dBm_best']:7.1f}..{r['dBm_worst']:7.1f} dBm  margin(worst) {r['margin_to_m100_worst_dB']:6.1f}")
print('carrier-derived:'); [print('  ', c) for c in cd]
print('baseband aliases (<=10 MHz):', len(bb))
seen = set()
for b in bb:
    if b['mode'].startswith('RF') and b['n'] <= 6: print('  ', b['source'], '| fs', b['fs'], '| n', b['n'], '|', b['f_MHz'], '->', b['alias_MHz'])
