"""Measured rail movement during actual comparator regeneration; no frozen-input claim."""
import hashlib, json
from pathlib import Path
import numpy as np

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()
from analyze_sar_full_aperture import aperture_events

def main():
    R = Path(__file__).resolve().parents[3]
    P = R / 'projects/programmable_transceiver_platform'
    e = P / 'evidence/sar-reservoir-double.json'
    audit = json.loads(e.read_text())
    assert audit['completed']
    rows = []
    for label, folder in [('baseline', 'sar-command-baseline'), ('double', 'sar-reservoir-double')]:
        w = R / ('scratch/transceiver-' + folder)
        result = json.loads((w / 'result.json').read_text())
        p = w / 'baseline.dat'
        assert sha(p) == result['artifacts_sha256']['.dat'] and result['returncode'] == 0 and (not result['timed_out'])
        with p.open() as f:
            h = f.readline().lower().split()
        a = np.loadtxt(p, skiprows=1)
        events = aperture_events(a, h, [(70.5, 72.4), (75.5, 77.4)])
        rows.append(dict(variant=label, waveform_sha256=sha(p), events=events))
    out = dict(source_evidence_sha256=sha(e), results=rows, limitations=['First crossing of 90% output differential is a timing diagnostic, not an effective sampling instant.', 'Residue motion includes reference response, comparator kickback and other coupled effects; no causal decomposition.', 'No noise/mismatch or complete-code accuracy qualification.'])
    (P / 'evidence/sar-reference-aperture.json').write_text(json.dumps(out, indent=2) + '\n')
    for r in rows:
        for event in r['events']:
            print(r['variant'], event)
if __name__ == '__main__':
    main()
