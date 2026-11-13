#!/usr/bin/env python3
"""E5: mode steps (stopped 15 mW -> full 0.98 W and back). Average-current envelope steps through the same network,
solved as a periodic trapezoid (period 8 us, 4 us on) by Fourier synthesis (linear network: exact for the envelope;
the per-cycle packet ripple is E3/E4 and adds on top).
 a) digital clock enable/disable: 0 -> I_dig in one core clock cycle (12.8 ns)
 b) D2H payload start/stop: 0 -> I_host in one UI pair (6.4 ns)
 c) a + b together (worst simultaneous start)
 d) rfdriver TDD on/off: 61.7 mA with the measured wake (1.2 us 10 %-settle) and an abrupt 50 ns variant
 e) island enable inrush: hand estimate from the soft-start peak (62 mA, 2.6-4.6 us rail rise) x low-frequency Z."""
import json, numpy as np
import model as M, core as C, loads as LD
T = 8e-6; NH = 1500; t = np.arange(8000)/8000*T
def trap_coef(k, tr, ton=4e-6):
    """Fourier coefficient (complex, for exp(+j 2 pi k t / T)) of a unit trapezoid: ramp up tr from t=1us, ramp down tr."""
    w = 2*np.pi*k/T
    # derivative = (1/tr) on [t0, t0+tr], -(1/tr) on [t1, t1+tr]
    t0 = 1e-6; t1 = t0+ton
    d = (np.exp(-1j*w*t0)-np.exp(-1j*w*(t0+tr))-np.exp(-1j*w*t1)+np.exp(-1j*w*(t1+tr)))/(1j*w*tr*T)
    return d/(1j*w)
res = {}
PLANS = {'none': C.decap_plan('none'), '3nF_spread': C.decap_plan('uniform', 3.0), 'ap49_low': C.decap_plan('ap49', frac=0.3, dig_fill_nF=0.45),
         'ap49_low+1.5nF_macro': C.decap_plan('ap49', frac=0.3, dig_fill_nF=1.95)}
F = np.arange(1, NH+1)/T
for plan, d in PLANS.items():
    for b in ('opt', 'nom', 'pess'):
        n, info, ports, vict = C.full(M.pset(b), decap=d)
        names, Zc, Zg = C.transfer(n, info, ports, vict, F)
        idig = {'opt': 24.5e-3, 'nom': 60e-3, 'pess': 81.79e-3}[b]; ihost = {'opt': 95.24e-3*0.7, 'nom': 116.82e-3, 'pess': 116.82e-3}[b]
        def wave(port, amp, tr, v):
            vi = names.index(v); pi = C.PORTS.index(port); w = np.zeros(len(t))
            for k in range(1, NH+1):
                c = trap_coef(k, tr)*amp*Zc[k-1, vi, pi]
                w += 2*(c*np.exp(2j*np.pi*k*t/T)).real
            return w
        r = {}
        for v in ('dig', 'core_bias', 'por', 'qvco', 'refbuf'):
            wa = wave('dig', idig, 12.8e-9, v); wb = wave('d2h0', ihost, 6.4e-9, v)
            wd = wave('rfd', 61.7e-3, 1.2e-6, v); wd2 = wave('rfd', 61.7e-3, 50e-9, v)
            def dyn(w):
                # dynamic excursion beyond the settled levels: undershoot after turn-on, overshoot after turn-off
                on = w[(t > 4.0e-6) & (t < 4.9e-6)].mean(); off = w[(t > 7.0e-6)].mean()
                return dict(static_mV=float((off-on)*1e3), undershoot_mV=float((on-w[(t > 0.9e-6) & (t < 4.9e-6)].min())*1e3),
                            overshoot_mV=float((w[(t > 4.9e-6)].max()-off)*1e3))
            r[v] = dict(digital_enable=dyn(wa), d2h_start=dyn(wb), both=dyn(wa+wb), rfdriver_wake_1p2us=dyn(wd), rfdriver_abrupt_50ns=dyn(wd2))
        res[f'{plan}|{b}'] = r
        x = r['dig']; y = r['core_bias']
        print(f"{plan:22s} {b:4s} macro: dig-enable static {x['digital_enable']['static_mV']:5.1f} under {x['digital_enable']['undershoot_mV']:6.1f} over {x['digital_enable']['overshoot_mV']:6.1f} | "
              f"both static {x['both']['static_mV']:5.1f} under {x['both']['undershoot_mV']:6.1f} over {x['both']['overshoot_mV']:6.1f} || core_bias both under {y['both']['undershoot_mV']:6.1f} over {y['both']['overshoot_mV']:6.1f} "
              f"| rfdrv 1.2us under {r['qvco']['rfdriver_wake_1p2us']['undershoot_mV']:5.2f} static {r['qvco']['rfdriver_wake_1p2us']['static_mV']:5.1f} (qvco tap) abrupt under {r['qvco']['rfdriver_abrupt_50ns']['undershoot_mV']:5.1f}")
json.dump(res, open('out/e5_steps.json', 'w'), indent=0)
