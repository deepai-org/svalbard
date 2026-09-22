"""Audit existing high-target DC evidence before repeating a polarity substitution.

No simulation or dynamic-equivalence claim. Historical provenance limitations stay.
"""
import hashlib
import json
from pathlib import Path
import numpy as np

R = Path(__file__).resolve().parents[3]
P = R / 'projects/programmable_transceiver_platform'
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

rows = []
inputs = {}
for tag, stem in [('reference-buffer-dc', 'buffer_scaled'),
                  ('reference-buffer-complement-dc', 'buffer_complement')]:
    evidence = P / 'evidence' / (tag + '-screen.json')
    inputs[str(evidence.relative_to(R))] = sha(evidence)
    old = P / 'analog/reference' / (stem + '.spice')
    tuned = P / 'analog/reference' / (stem + '_tune.spice')
    old_lines = old.read_text().splitlines()
    new_lines = tuned.read_text().splitlines()
    # Explicitly enumerate every circuit element: compensation is a series RC
    # terminating in an ideal capacitor, hence no DC conduction through RC.
    elements = lambda lines: [s for s in lines if s and s[0].upper() in 'XRC']
    oe, ne = elements(old_lines), elements(new_lines)
    assert len(oe) == len(ne) == 9
    assert oe[:7] == ne[:7] and all(s.startswith('X') for s in oe[:7])
    assert oe[7:] == ['RC X Z {100/S}', 'CC Z OUT {CC*S}']
    assert ne[7:] == ['RC X Z {RZ/S}', 'CC Z OUT {CC*S}']
    for p in (old, tuned): inputs[str(p.relative_to(R))] = sha(p)
    d = json.loads(evidence.read_text())
    assert d['source_sha256']['/screen/reference/' + stem + '.spice'] == sha(old)
    selected = [c for c in d['cases'] if c['target_v'] == 2.15 and c['scale'] == 4]
    assert {c['direction'] for c in selected} == {-1, 1}
    for c in selected:
        assert c['returncode'] == 0
        folder = R / 'scratch' / ('transceiver-' + tag)
        for ext in ('.spice', '.dat', '.log'):
            p = folder / (c['name'] + ext)
            assert sha(p) == c['artifacts_sha256'][ext]
            inputs[str(p.relative_to(R))] = sha(p)
        deck = (folder / (c['name'] + '.spice')).read_text()
        assert 'VT TARGET 0 2.15' in deck and 'S=4' in deck
        a = np.loadtxt(folder / (c['name'] + '.dat'), skiprows=1)
        assert a.shape == (81, 5) and np.isfinite(a).all()
        a = a[np.argsort(a[:, 0])]
        assert np.allclose(a[:, 0], np.linspace(-.02, .02, 81), atol=1e-15, rtol=0)
        measurements = []
        for current in (-.003, 0, .003):
            k = int(np.argmin(abs(a[:, 0] - current)))
            error = float(1000 * (a[k, 1] - 2.15))
            reported = min(c['operating_points'], key=lambda x: abs(x['load_ma'] - current*1000))
            assert abs(error - reported['error_mv']) < 1e-9
            measurements.append(dict(load_ma=current*1000, error_mv=error))
        rows.append(dict(topology=stem, direction=c['direction'], measurements=measurements))
result = dict(status='historical_DC_evidence_and_transistor_topology_audited',
    cases=rows, inputs_sha256=inputs,
    decision='Do not repeat the unchanged NMOS-input/output buffer as a direct high-reference replacement.',
    next_question='Can input-stage headroom and bidirectional output regulation be improved together without excessive power or unstable reservoir loading?',
    limitations=[
        'Compensation changes do not change ideal DC equations; dynamic behavior is not equivalent.',
        'Historical source hashes were recorded after simulation, not a full before/after model provenance chain.',
        'Ideal targets and bias currents; no mismatch, noise, startup or parasitic qualification.',
        'This rejects reuse of this existing topology at these conditions, not all NMOS-input amplifier designs.'
    ])
(P / 'evidence/reference-polarity-reuse.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(dict(status=result['status'], cases=rows), indent=2))
