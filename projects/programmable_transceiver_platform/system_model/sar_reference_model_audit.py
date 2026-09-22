"""Audit whether recorded rail span alone explains physical SAR decisions."""
import hashlib
import json
from pathlib import Path

P=Path(__file__).resolve().parents[1]
source=P/'evidence/sar-physical-divergence.json'
raw=json.loads(source.read_text())
assert raw['source_sha256']==hashlib.sha256((P/'evidence/sar-driver-physical.json').read_bytes()).hexdigest()
assert raw['script_sha256']==hashlib.sha256((P/'system_model/sar_physical_divergence.py').read_bytes()).hexdigest()
rows=[]
for frame in raw['results']:
    steps=frame['steps']
    # Evaluate at observed trial codes, not a fabricated counterfactual path.
    disagrees=[s['bit'] for s in steps if (s['measured_rail_residue_v']<=0)!=s['actual_keep']]
    nominal=[s['bit'] for s in steps if (s['nominal_rail_residue_v']<=0)!=s['actual_keep']]
    vulnerable=[s['bit'] for s in steps if abs(s['unexplained_residue_v'])>=abs(s['measured_rail_residue_v'])]
    rows.append(dict(case=frame['case'],hold_ns=frame['hold_ns'],
        nominal_sign_disagreement_bits=nominal,rail_only_sign_disagreement_bits=disagrees,
        residual_exceeds_rail_margin_bits=vulnerable,
        maximum_unexplained_residue_v=max(abs(s['unexplained_residue_v']) for s in steps),
        minimum_actual_decision_margin_v=min(abs(s['actual_residue_v']) for s in steps)))
report=dict(source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),frames=rows,
    status='observed_history_model_adequacy_audit',
    limitations=['Uses observed trial codes and rail traces; not a predictive conversion model.',
      'Unexplained residual combines omitted mechanisms, not an independent random offset.',
      'Nine conversions cannot establish bounds or generalization to modulated input.',
      'Do not replay these rails onto changed code histories as if loading were unchanged.'])
(P/'evidence/sar-reference-model-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(rows,indent=2))
