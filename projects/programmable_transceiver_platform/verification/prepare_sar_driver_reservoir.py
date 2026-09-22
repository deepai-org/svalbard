"""One-factor reservoir doubling on qualified physical-reference driver fixtures."""
import hashlib
import json
from pathlib import Path
R = Path(__file__).resolve().parents[3]
P = R/'projects/programmable_transceiver_platform'
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
e = P/'evidence/sar-driver-physical.json'
report = json.loads(e.read_text())
assert report['completed']
extra = 'XHR_EXTRA VH 0 pt_ref_reservoir_2048\nXLR_EXTRA VL 0 pt_ref_reservoir_2048\n'
needle = 'XLR VL 0 pt_ref_reservoir_2048\n'
for label in ('400', '100'):
    source = 'sar-driver-physical-'+label
    case = next(c for c in report['cases'] if c['name'] == source)
    b = R/('scratch/transceiver-'+source+'-prepared')
    w = R/('scratch/transceiver-'+source)
    assert sha(b/'manifest.json') == case['preparation_sha256']
    assert sha(w/'result.json') == case['result_sha256']
    result = json.loads((w/'result.json').read_text())
    assert result['sources_before'] == result['sources_after']
    s = (b/'baseline.spice').read_text()
    assert sha(b/'baseline.spice') == result['artifacts_sha256']['.spice']
    assert s.count(needle) == 1 and extra not in s
    candidate = s.replace(needle, needle+extra)
    assert candidate.replace(extra, '') == s
    out = R/('scratch/transceiver-sar-driver-reservoir-'+label+'-prepared')
    out.mkdir()
    (out/'baseline.spice').write_text(candidate)
    manifest = dict(candidate='Double reference reservoir with 2k sample-driver damping.',
        physical_source=source, amplitude_v=case['amplitude_v'],
        source_evidence_sha256=sha(e), baseline_preparation_sha256=sha(b/'manifest.json'),
        artifacts_sha256={'baseline.spice':sha(out/'baseline.spice')},
        qualification_plan=[
            'Require terminal clean completion, stable include hashes and exact capacitor-only reversal.',
            'Compare all 24 decisions, codes, acquisition and reference settling with the matched amplitude baseline.',
            'Assess first and later positive-input frames separately; do not average away history effects.'],
        limitations=['Adds approximately 0.1024 mm2 capacitor plate area before layout overhead.',
            'Reference targets, bias and phase controls remain ideal.',
            'Two input amplitudes do not establish transfer linearity, noise or 40 MS/s operation.'])
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(out)
