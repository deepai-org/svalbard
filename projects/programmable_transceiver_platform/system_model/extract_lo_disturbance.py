"""Extract a finite measured LO baseband trace; never periodically extend it."""
import hashlib
import json
from pathlib import Path
import numpy as np

P = Path(__file__).resolve().parents[1]
R = P.parents[1]
source = R / 'scratch/transceiver-lo-receiver-replay/replay.dat'
evidence = P / 'evidence/lo-receiver-replay.json'
prior = json.loads(evidence.read_text())
assert prior['completed']
hash_value = hashlib.sha256()
with source.open('rb') as f:
    for block in iter(lambda: f.read(1024 * 1024), b''):
        hash_value.update(block)
assert hash_value.hexdigest() == prior['artifacts_sha256']['.dat']
with source.open() as f:
    header = f.readline().lower().split()
columns = [0] + [header.index(n) for n in ['v(fip)', 'v(fin)', 'v(fqp)', 'v(fqn)']]
a = np.loadtxt(source, skiprows=1, usecols=columns)
t = a[:, 0]
assert np.isfinite(a).all() and np.all(np.diff(t) > 0)
assert t[0] < 512e-9 and t[-1] >= 1024e-9
mask = (t >= 512e-9) & (t <= 1024e-9)
t = t[mask]
iq = (a[mask, 1] - a[mask, 2]) + 1j * (a[mask, 3] - a[mask, 4])
# Uniform grid keeps the artifact small. Compare two resolutions independently.
reports = []
for step in [100e-12, 50e-12]:
    grid = np.arange(513e-9, 1023e-9, step)
    values = np.interp(grid, t, iq.real) + 1j * np.interp(grid, t, iq.imag)
    angle = 2 * np.pi * 19.53125e6 * grid
    basis = np.column_stack([np.ones(len(grid)), np.cos(angle), np.sin(angle)])
    control_coef = np.array([.02 + .01j, .03 - .004j, -.007 + .002j])
    control_fit = np.linalg.lstsq(basis, basis @ control_coef, rcond=None)[0]
    assert np.allclose(control_fit, control_coef, rtol=1e-12, atol=1e-14)
    coef = np.linalg.lstsq(basis, values, rcond=None)[0]
    residual = values - basis @ coef
    reports.append(dict(step_ps=step * 1e12,
                        ac_rms_v=float(np.sqrt(np.mean(abs(values - values.mean()) ** 2))),
                        fundamental_fit_residual_rms_v=float(np.sqrt(np.mean(abs(residual) ** 2))),
                        max_residual_v=float(abs(residual).max())))
# Fine-grid artifact includes real I/Q phase and harmonics within its resolution.
out = P / 'evidence/lo-disturbance-trace.npz'
np.savez_compressed(out, time_s=grid, i_v=values.real, q_v=values.imag)
report = dict(status='finite_zero_rf_replay_trace_only',
              source_sha256=hash_value.hexdigest(),
              evidence_sha256=hashlib.sha256(evidence.read_bytes()).hexdigest(),
              script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              trace_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
              start_s=float(grid[0]), stop_s=float(grid[-1]), samples=len(grid),
              resolution_comparison=reports,
              limitations=['Specific seeded zero-RF replay; not autonomous full-loop qualification.',
                           'No periodic extension or steady-state assumption justified.',
                           'Uniform interpolation is not an anti-alias filter.',
                           'RF-driven superposition and physical ADC sampling remain unverified.'])
(P / 'evidence/lo-disturbance-trace.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(reports, indent=2))
