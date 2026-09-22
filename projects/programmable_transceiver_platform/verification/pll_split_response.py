#!/usr/bin/env python3
"""Explain early feedback response; conditional poles are not lock evidence."""
import hashlib
import json
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[3]
P = ROOT / 'projects/programmable_transceiver_platform'
W = ROOT / 'scratch/transceiver-closed-loop-split'
validated = json.loads((P / 'evidence/closed-loop-split-screen.json').read_text())
assert hashlib.sha256((W / 'closed.dat').read_bytes()).hexdigest() == validated['artifacts_sha256']['.dat']
a = np.loadtxt(W / 'closed.dat', skiprows=1)
t = a[:, 0]
def edges(col):
    v = a[:, col]
    i = np.flatnonzero((v[:-1] < 1.65) & (v[1:] >= 1.65))
    return t[i] + (1.65-v[i]) * np.diff(t)[i] / np.diff(v)[i]
def integral(col, lo, hi):
    inside = (t > lo) & (t < hi)
    ts = np.r_[lo, t[inside], hi]
    return float(np.trapezoid(np.interp(ts, t, a[:, col]), ts))
ref, fb = edges(17), edges(9)
cycles = []
for lo, hi in zip(ref[:-1], ref[1:]):
    following = fb[(fb > lo) & (fb < hi)]
    assert len(following) == 1, 'Unexpected feedback edge count; reassess pairing'
    cycles.append(dict(reference_edge_ns=float(lo*1e9), feedback_edge_ns=float(following[0]*1e9), feedback_lag_ns=float((following[0]-lo)*1e9), pump_charge_fc=integral(16,lo,hi)*1e15))
assert len(cycles) == 4
slopes = []
for name in ('vco-split-lower.json', 'vco-split-tuning.json'):
    data = json.loads((P / 'evidence' / name).read_text())
    slopes.extend(data['slopes_hz_per_v'])
# Include the gap between the separately run lower and upper sweeps.
lower = json.loads((P / 'evidence/vco-split-lower.json').read_text())['cases'][-1]
upper = json.loads((P / 'evidence/vco-split-tuning.json').read_text())['cases'][0]
slopes.append((upper['frequency_hz']-lower['frequency_hz'])/(upper['control_v']-lower['control_v']))
cases = []
for kv in sorted(slopes):
    I, N, R, Cz, Cp = 20e-6, 128, 1e4, 50e-12, 2e-12
    K = I * kv / N
    poles = np.roots([R*Cp*Cz, Cp+Cz, K*R*Cz, K])
    stable = bool(np.all(poles.real < 0))
    cases.append(dict(kv_hz_per_v=kv, poles_rad_per_s=[[float(p.real),float(p.imag)] for p in poles], all_poles_left_half_plane=stable, four_time_constant_envelope_s=float(4/min(-poles.real)) if stable else None))
r = dict(status='early_phase_catchup_and_conditional_linear_analysis_not_lock', cycles=cycles, conditional_linear_cases=cases, waveform_sha256=validated['artifacts_sha256']['.dat'], interpretation='Feedback remains later than reference after reset; positive pump charge is consistent with that phase lag even though instantaneous oscillator frequency is above target. Lag and cycle charge decrease over the four complete observed cycles. This is early catchup, not acquisition proof.', limitations=['Initial divider phase, PFD reset and precharge strongly affect this short record.', 'Edge pairing is valid for this record only; longer tests must account for cycle slips.', 'Secant slopes treated as constant differential gains in an ideal averaged 20uA pump/divide128 model.', 'Linear poles omit switching delay, pump asymmetry, real VCO admittance, saturation, noise and process variation.', 'No physical or statistical bound follows from the sampled gain range.'])
(P / 'evidence/pll-split-response.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
