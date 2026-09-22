#!/usr/bin/env python3
"""Controlled horizon extension; report fit sensitivity without inventing pass limits."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
P = ROOT / 'projects/programmable_transceiver_platform'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

records = {}
provenance = {}
for name in ('bb-connected', 'bb-connected-settling'):
    audit_path = P / 'evidence' / (name + '.json')
    analysis_path = P / 'evidence' / (name + '-conversion.json')
    audit = json.loads(audit_path.read_text())
    analysis = json.loads(analysis_path.read_text())
    assert audit['completed'] and analysis['completed']
    assert analysis['audit_sha256'] == sha(audit_path)
    work = ROOT / 'scratch' / ('transceiver-' + name)
    for case in audit['provenance']['cases']:
        for ext, digest in case['artifacts_sha256'].items():
            assert sha(work / (case['name'] + ext)) == digest
    records[name] = (audit, analysis, work)
    provenance[name] = dict(audit_sha256=sha(audit_path), analysis_sha256=sha(analysis_path))
short, long = records.values()
assert short[0]['provenance']['source_sha256_before'] == long[0]['provenance']['source_sha256_before']
for case in ('zero', 'tone'):
    original = (short[2] / (case + '.spice')).read_text()
    extended = (long[2] / (case + '.spice')).read_text()
    assert extended.count('tran 2p 401n 0 2p uic') == 1
    assert extended.replace('tran 2p 401n 0 2p uic', 'tran 2p 201n 0 2p uic') == original

def select(record, case, window, order=8):
    row = next(c for c in record[1]['cases'] if c['name'] == case)
    return next(f for f in row['fits'] if f['window_ns'] == window and f['lo_harmonic_fit_order'] == order)

metrics = ('filter_i_peak_v', 'filter_q_peak_v', 'filter_i_residual_rms_v',
           'filter_q_residual_rms_v', 'filter_q_over_i', 'filter_q_phase_deg')
rows = []
for case in ('zero', 'tone'):
    early = select(short, case, [120, 200])
    repeat = select(long, case, [120, 200])
    previous = select(long, case, [240, 320])
    late = select(long, case, [320, 400])
    broad = select(long, case, [240, 400])
    row = dict(name=case, horizon_extension_same_window_delta={
        k: repeat[k] - early[k] for k in metrics if early[k] is not None},
        late_window_delta={k: late[k] - previous[k] for k in metrics if late[k] is not None},
        last_window={k: late[k] for k in metrics},
        combined_late_window={k: broad[k] for k in metrics})
    if case == 'tone':
        row['late_amplitude_change_fraction'] = {
            channel: late['filter_' + channel + '_peak_v'] / previous['filter_' + channel + '_peak_v'] - 1
            for channel in ('i', 'q')}
    rows.append(row)
out = dict(completed=True, declared_change='201 ns to 401 ns horizon only',
           provenance=provenance, cases=rows,
           limitations=['Diagnostic window sensitivity only; no requirement-derived settling limit allocated.',
                        'No-tone fitted components and deterministic residuals are not intrinsic noise.',
                        'Seeded/prebiased nominal circuit; no ADC load, autonomous PLL, startup or receiver qualification.'])
(P / 'evidence/bb-settling-comparison.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps(out, indent=2))
