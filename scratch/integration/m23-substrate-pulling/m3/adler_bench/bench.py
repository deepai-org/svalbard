#!/usr/bin/env python3
"""Known-answer bench for the pulling measurement (mandate: prove the bench small).  Ideal parallel RLC (2.4 GHz, Q = 5) with a
tanh negative conductance, injected current I_inj at f0 + D.  Adler: one-sided lock range f_L = f0/(2Q) * I_inj/I_osc with
I_osc = fundamental of the limiter current.  Checks: (1) D >> f_L -> FM amplitude at D equals f_L; (2) D < f_L locks;
(3) must-fail: D just above f_L must NOT lock; (4) null: I_inj = 0 -> no FM at D."""
import subprocess, numpy as np, json, os
os.environ.setdefault('OMP_NUM_THREADS', '1')
F0, Q, L = 2.4e9, 5.0, 2.65e-9
C = 1/((2*np.pi*F0)**2*L); RP = Q*2*np.pi*F0*L; IMAX = 2e-3
def sim(name, iinj, finj, T):
    d = f"""* adler {name}
L1 a 0 {L}
C1 a 0 {C} ic=0.05
R1 a 0 {RP}
B1 a 0 I = -{IMAX}*tanh(v(a)*{6/RP}/{IMAX})
I2 0 a sin(0 {iinj} {finj})
B3 ref 0 V = sin(6.283185307179586*{finj}*time)
.option method=trap reltol=1e-5
.control
tran 1p {T} 0 1p uic
wrdata {name}.txt v(a) v(ref) i(l1)
quit
.endc
.end
"""
    open(name+'.cir', 'w').write(d); subprocess.run(['ngspice', '-b', name+'.cir'], capture_output=True)
    return np.loadtxt(name+'.txt')
def edges(t, v):
    k = np.where((v[:-1] < 0) & (v[1:] >= 0))[0]; return t[k]-v[k]*(t[k+1]-t[k])/(v[k+1]-v[k])
def meas(x, ts, D=None):
    t, v = x[:, 0], x[:, 1]; m = t > ts; e = edges(t[m], v[m]); f0 = 1/np.polyfit(np.arange(len(e)), e, 1)[0]
    amp = None
    if D:
        fi = 1/np.diff(e); tm = (e[1:]+e[:-1])/2
        A = np.array([np.ones_like(tm), np.sin(2*np.pi*D*tm), np.cos(2*np.pi*D*tm)]).T; c, *_ = np.linalg.lstsq(A, fi, rcond=None); amp = float(np.hypot(c[1], c[2]))
    return f0, amp, float(np.abs(v[m]).max())
out = {}
x = sim('free', 0, F0, 150e-9); f0, _, va = meas(x, 50e-9)
# limiter fundamental current from the tank: I_osc = V/Rp
iosc = va/RP; iinj = 50e-6; fl = f0/(2*Q)*iinj/iosc
out['free'] = dict(f0_MHz=f0/1e6, v_amp=va, i_osc_mA=iosc*1e3, adler_fL_MHz=fl/1e6)
D = 40e6; x = sim('far', iinj, f0+D, 250e-9)
fa, amp, _ = meas(x, 50e-9, np.sqrt(D**2-fl**2))                 # beat frequency is sqrt(D^2 - fL^2)
out['far'] = dict(D_MHz=D/1e6, fm_amp_MHz=amp/1e6, ratio_to_adler=amp/fl, mean_shift_MHz=(fa-f0)/1e6, adler_mean_shift_MHz=(D-np.sqrt(D**2-fl**2))/1e6)
x = sim('null', 0, f0+D, 250e-9); _, amp0, _ = meas(x, 50e-9, D); out['null'] = dict(fm_amp_MHz=amp0/1e6)
def locked(x, finj, ts):
    t = x[:, 0]; m = t > ts; ea = edges(t[m], x[m, 1]); er = edges(t[m], x[m, 3])
    ph = np.interp(ea, er, np.arange(len(er)))-np.arange(len(ea)); ph = ph[ea < er[-1]]; return float(np.ptp(ph[len(ph)//2:]))
x = sim('in', iinj, f0+0.6*fl, 700e-9); out['inside_0.6fL'] = dict(phase_span_cycles=locked(x, 0, 100e-9))
x = sim('out', iinj, f0+1.3*fl, 700e-9); out['outside_1.3fL'] = dict(phase_span_cycles=locked(x, 0, 100e-9))
out['pass'] = bool(abs(out['far']['ratio_to_adler']-1) < 0.15 and out['null']['fm_amp_MHz'] < 0.05*fl/1e6
                   and out['inside_0.6fL']['phase_span_cycles'] < 0.05 and out['outside_1.3fL']['phase_span_cycles'] > 0.5)
print(json.dumps(out, indent=1)); json.dump(out, open('adler_bench.json', 'w'), indent=1)
