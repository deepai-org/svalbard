#!/usr/bin/env python3
"""Audit the controlled VCO substitution and short actual-loop transient."""
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
P = ROOT / 'projects/programmable_transceiver_platform'
W = ROOT / 'scratch/transceiver-closed-loop-split'
r = json.loads((W / 'result.json').read_text())
for suffix, digest in r['artifacts_sha256'].items():
    assert hashlib.sha256((W / ('closed' + suffix)).read_bytes()).hexdigest() == digest
original = (ROOT / 'scratch/transceiver-closed-loop/closed.spice').read_text()
expected = original.replace('/vco/ring_vco.spice', '/screen/pll/ring_vco_split.spice').replace('/screen/rf_rx_candidate.spice', '/screen/rf_rx_candidate_split.spice').replace('0 pt_rf_rx_candidate', '0 REGEN pt_rf_rx_candidate_split').replace('.control', 'VREGEN REGEN 0 1.08\n.control')
# Source placement is immaterial; require exact equality after moving only VREGEN.
actual = (W / 'closed.spice').read_text()
assert actual.count('VREGEN REGEN 0 1.08\n') == 1
assert actual.replace('VREGEN REGEN 0 1.08\n', '') == expected.replace('VREGEN REGEN 0 1.08\n', '')
assert 'VC CTRL 0' not in actual
for stage in range(1, 8):
    assert f'XD{stage} ' in actual
for connection in ('XPFD REF FB RN UP DN', 'XCP UP DN PUMP', 'VSENSE PUMP CTRL 0', 'XFILT CTRL 0 pt_loop_filter'):
    assert connection in actual

a = np.loadtxt(W / 'closed.dat', skiprows=1)
assert a.shape[1] == 18 and np.isfinite(a).all()
assert a[-1, 0] > 320e-9 and np.all(np.diff(a[:, 0]) > 0)
for row in r['windows']:
    lo, hi = row['window_ns']
    w = a[(a[:, 0] >= lo * 1e-9) & (a[:, 0] <= hi * 1e-9)]
    t, v = w[:, 0], w[:, 1]
    i = np.flatnonzero((v[:-1] < 0) & (v[1:] >= 0))
    edges = t[i] - v[i] * np.diff(t)[i] / np.diff(v)[i]
    assert len(edges) > 3
    assert np.isclose(row['vco_frequency_hz'], 1 / np.mean(np.diff(edges)), rtol=1e-10)
    assert np.allclose(row['control_range_v'], [w[:, 14].min(), w[:, 14].max()], rtol=1e-10)
    assert np.allclose(row['gate_range_v'], [w[:, 10].min(), w[:, 10].max()], rtol=1e-10)
    charge = np.trapezoid(w[:, 16], t)
    stored = 2e-12 * (w[-1, 14] - w[0, 14]) + 50e-12 * (w[-1, 15] - w[0, 15])
    row['pump_charge_fc'] = float(charge * 1e15)
    # Difference includes the real VCO control input, not just numerical error.
    row['pump_minus_filter_charge_fc'] = float((charge - stored) * 1e15)
late = a[a[:, 0] >= 100e-9]
r['controlled_vco_substitution_checked'] = True
r['actual_feedback_connectivity_checked'] = True
r['bias_guard_pass'] = bool(late[:, 10].min() > 1.4 and late[:, 10].max() < 1.6)
r['pump_filter_control_range_v'] = [float(late[:, 14].min()), float(late[:, 14].max())]
r['sampled_tuning_envelope_v'] = [0.98, 1.30]
r['sampled_tuning_envelope_exceeded'] = bool(late[:, 14].min() < .98 or late[:, 14].max() > 1.30)
r['pll_lock_established'] = False
r['limitations'].append('Seven fixed-control samples bracket a range; they do not establish continuous monotonicity or a safe capture envelope.')
assert r['bias_guard_pass'], 'Invalid LNA bias'
(P / 'evidence/closed-loop-split-screen.json').write_text(json.dumps(r, indent=2) + '\n')
print(json.dumps(r, indent=2))
