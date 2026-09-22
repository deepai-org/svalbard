"""Independent nominal DC plus AC prediction; no transient coefficient fitting."""
import hashlib
import json
import math
from pathlib import Path

P = Path(__file__).resolve().parents[1]
R = P.parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ac_path = P/'evidence/reference-ac-charge-prediction.json'
    dc_path = P/'evidence/load-terminal-dc.json'
    ac = json.loads(ac_path.read_text())
    dc = json.loads(dc_path.read_text())
    for name, digest in ac['source_hashes'].items():
        path = P/('system_model' if name.endswith('.py') else 'evidence')/name
        assert sha(path) == digest, f'Stale AC source: {name}'
    assert dc['source_hashes_before'] == dc['source_hashes_after']
    for ext, digest in dc['artifacts_sha256'].items():
        assert sha(R/'scratch/transceiver-load-terminal-dc'/('probe'+ext)) == digest
    assert sha(P/'analog/reference/load_terminal_dc.py') == dc['source_hashes_before']['/screen/reference/load_terminal_dc.py']
    raw_ac = json.loads((P/'evidence/load-terminal-ac.json').read_text())
    for name, digest in dc['source_hashes_before'].items():
        if name.startswith('/foss/pdks/'):
            assert raw_ac['source_hashes_before'][name] == digest
    currents = {}
    for rail, kind, voltage in [('xhigh', 'n', 2.15), ('xlow', 'p', 1.15)]:
        case, = [c for c in dc['cases'] if c['type'] == kind and c['drain_v'] == voltage]
        assert abs(case['terminal_kcl_error_a']) < 1e-14
        assert abs(case['drain_minus_channel_a']+case['body_current_a']) < 1e-14
        currents[rail] = case['drain_minus_channel_a']
    rows = []
    for row in ac['rows']:
        duration = {'preclock': .2e-9, 'switching': 1.1e-9}[row['window']]
        dc_charge = currents[row['rail']]*duration
        predicted = row['predicted_charge_c']+dc_charge
        rows.append(dict(row, ac_only_error_c=row['error_c'], duration_s=duration,
                         nominal_dc_charge_c=dc_charge, predicted_charge_c=predicted,
                         error_c=predicted-row['observed_charge_c']))
    assert len(rows) == 96
    summaries = []
    for rail in currents:
        group = [r for r in rows if r['rail'] == rail]
        summaries.append(dict(rail=rail, nominal_excess_current_a=currents[rail],
            maximum_error_c=max(abs(r['error_c']) for r in group),
            rms_error_c=math.sqrt(sum(r['error_c']**2 for r in group)/len(group)),
            maximum_ac_only_error_c=max(abs(r['ac_only_error_c']) for r in group),
            rms_ac_only_error_c=math.sqrt(sum(r['ac_only_error_c']**2 for r in group)/len(group))))
    report = dict(coefficients_fitted_to_transient=False, physical_qualification=False,
        source_hashes={p.name:sha(p) for p in (Path(__file__), ac_path, dc_path)},
        summaries=summaries, rows=rows, limitations=[
            'Fixed nominal DC current; drain/gate dependence over each window is omitted.',
            'Measured voltage endpoints remain inputs; this is not an autonomous reference model.',
            'Same open PDK for all experiments, not independent silicon validation.',
            'Separate diagnostic; frozen independent-amplitude comparators are unchanged.'])
    (P/'evidence/reference-ac-dc-charge-prediction.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps(summaries, indent=2))

if __name__ == '__main__':
    main()
