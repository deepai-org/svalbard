#!/usr/bin/env python3
"""Locate probe-induced differences without changing the reproduction gate."""
import hashlib
import json
from pathlib import Path
import numpy as np
R = Path(__file__).resolve().parents[3]
P = R / 'projects/programmable_transceiver_platform'
E = P / 'evidence/cdac-branch-replay.json'
e = json.loads(E.read_text())
assert e['completed'] and e['same_time_grid']
arrays = []
for name, hashes in [('transceiver-cdac-branch-replay', e['provenance']['artifacts_sha256']),
                     ('transceiver-adc-reference-current', e['baseline_artifacts_sha256'])]:
    root = R / 'scratch' / name
    for ext, expected in hashes.items():
        assert hashlib.sha256((root / ('frames' + ext)).read_bytes()).hexdigest() == expected
    p = root / 'frames.dat'
    with p.open() as f:
        header = f.readline().lower().split()
    a = np.loadtxt(p, skiprows=1)
    assert a.shape[1] == len(header) and np.isfinite(a).all()
    arrays.append((header, a))
(h, a), (bh, b) = arrays
assert np.array_equal(a[:, 0], b[:, 0])
t = a[:, 0]
rows = []
for n in ['v(hp)', 'v(hn)', 'v(q_hp)', 'v(q_hn)', 'v(vh)', 'v(vl)', 'v(ip)', 'v(in)']:
    err = abs(a[:, h.index(n)] - b[:, bh.index(n)])
    peak = int(err.argmax())
    bad = np.flatnonzero(err >= e['analog_tolerance_v'])
    decisions = []
    for hold in (70, 120, 170):
        for bit in range(8):
            start = hold + 5 * bit + .2
            mask = (t >= start * 1e-9) & (t <= (start + .15) * 1e-9)
            assert mask.any()
            decisions.append(float(err[mask].max()))
    rows.append(dict(node=n, max_error_v=float(err[peak]), peak_time_ns=float(t[peak]*1e9),
                     samples_at_or_above_limit=int(bad.size),
                     first_exceedance_ns=float(t[bad[0]]*1e9) if bad.size else None,
                     last_exceedance_ns=float(t[bad[-1]]*1e9) if bad.size else None,
                     max_predecision_error_v=max(decisions)))
out = dict(reproduction_evidence_sha256=hashlib.sha256(E.read_bytes()).hexdigest(),
           analog_reproduction_verified=e['analog_reproduction_verified'], nodes=rows,
           interpretation='Localization only; original 10uV gate remains failed. No branch attribution authorized.',
           next_test='Matched baseline and sensor runs with tighter solver tolerances; compare convergence of both before attributing currents.',
           limitations=['Post-inspection window audit is diagnostic, not a replacement acceptance criterion.',
                        'Matching captured codes and rail KCL does not establish unchanged analog trajectories.'])
(P/'evidence/cdac-probe-difference.json').write_text(json.dumps(out, indent=2)+'\n')
print(json.dumps(rows, indent=2))
