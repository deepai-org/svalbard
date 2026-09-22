#!/usr/bin/env python3
"""Verify extended run provenance and characterize response without claiming lock."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[3]
P = ROOT / 'projects/programmable_transceiver_platform'
parser = argparse.ArgumentParser(); parser.add_argument('--settling', action='store_true'); args = parser.parse_args()
tag = 'settling' if args.settling else 'extended'
stop_ns = 3201 if args.settling else 1201
W = ROOT / ('scratch/transceiver-closed-loop-' + tag)
B = ROOT / 'scratch/transceiver-closed-loop-split'
r = json.loads((W / 'result.json').read_text())
for suffix, digest in r['artifacts_sha256'].items():
    assert hashlib.sha256((W / ('closed' + suffix)).read_bytes()).hexdigest() == digest
base = (B / 'closed.spice').read_text()
actual = (W / 'closed.spice').read_text()
# Only observation duration and retained output vectors may differ.
reversed_deck = '\n'.join(line for line in actual.splitlines() if not line.startswith('save '))+'\n'
assert reversed_deck.replace(f'tran 2p {stop_ns}n 0 2p uic', 'tran 2p 321n 0 2p uic') == base
r['unchanged_circuit_and_timestep_checked'] = True
a = np.loadtxt(W / 'closed.dat', skiprows=1)
b = np.loadtxt(B / 'closed.dat', skiprows=1)
assert a.shape[1] == 18 and np.isfinite(a).all() and a[-1,0] > (stop_ns-1)*1e-9
assert np.all(np.diff(a[:,0]) > 0)
# Ignore the prior run's final endpoint, where stopping time can alter a timestep.
overlap = b[b[:,0] < 320e-9]
errors = [float(np.max(np.abs(np.interp(overlap[:,0], a[:,0], a[:,col])-overlap[:,col]))) for col in range(1,18)]
r['overlap_max_absolute_error_by_signal_column'] = errors
assert max(errors) < 1e-5, 'Changing save/duration altered early waveform; investigate before interpretation'

def edges(col, threshold):
    t, v = a[:,0], a[:,col]
    i = np.flatnonzero((v[:-1] < threshold) & (v[1:] >= threshold))
    return t[i] + (threshold-v[i])*np.diff(t)[i]/np.diff(v)[i]
ref = edges(17, 1.65)
fb = edges(9, 1.65)
r['reference_rising_edges_ns'] = (ref*1e9).tolist()
r['feedback_rising_edges_after_reset_ns'] = (fb[fb>90.1e-9]*1e9).tolist()
cycles = []
for lo,hi in zip(ref[:-1],ref[1:]):
    mask = (a[:,0]>lo)&(a[:,0]<hi)
    t = np.r_[lo,a[mask,0],hi]
    current = np.interp(t,a[:,0],a[:,16])
    cycles.append(dict(start_ns=float(lo*1e9), end_ns=float(hi*1e9), pump_charge_fc=float(np.trapezoid(current,t)*1e15), feedback_edges_inside=int(np.sum((fb>=lo)&(fb<hi)))))
r['reference_cycles'] = cycles
r['both_charge_polarities_observed'] = bool(any(c['pump_charge_fc']>0 for c in cycles) and any(c['pump_charge_fc']<0 for c in cycles))
for row in r['windows']:
    lo,hi = row['window_ns']
    mask = (a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)
    w = a[mask]
    e = edges(1,0)
    e = e[(e>=w[0,0])&(e<=w[-1,0])]
    assert len(e)>3
    assert np.isclose(row['vco_frequency_hz'],1/np.mean(np.diff(e)),rtol=1e-10)
    assert np.allclose(row['control_range_v'],[w[:,14].min(),w[:,14].max()],rtol=1e-10)
late = a[a[:,0]>=100e-9]
r['bias_guard_pass'] = bool(late[:,10].min()>1.4 and late[:,10].max()<1.6)
r['control_range_after_100ns_v'] = [float(late[:,14].min()),float(late[:,14].max())]
r['sampled_tuning_envelope_exceeded'] = bool(late[:,14].min()<.98 or late[:,14].max()>1.30)
r['pll_lock_established'] = False
r['limitations'].extend(['Observed pump reversal alone does not establish settling, lock, phase noise or robustness.', 'Sampled 0.98--1.30 V tuning envelope is not a continuously verified or process-qualified capture interval.'])
assert r['bias_guard_pass'], 'LNA bias invalidates interpretation'
(P/('evidence/closed-loop-'+tag+'-screen.json')).write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
