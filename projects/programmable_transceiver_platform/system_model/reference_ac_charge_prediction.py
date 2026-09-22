"""Predict transient load charge using independent AC derivatives, without fitting."""
import hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).resolve().parents[1];R=P.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
ac_path=P/'evidence/load-terminal-ac.json';ac=json.loads(ac_path.read_text())
assert ac['source_hashes_before']==ac['source_hashes_after']
for ext,h in ac['artifacts_sha256'].items():
 assert sha(R/'scratch/transceiver-load-terminal-ac-v2'/('probe'+ext))==h
base_path=P/'evidence/reference-load-charge-fit.json';base=json.loads(base_path.read_text())
bias_path=P/'evidence/reference-bias-observation.json';bias=json.loads(bias_path.read_text())
assert bias['reproduction_pass'] and bias['original_vectors_exact']
assert bias['parent_waveform_sha256']==base['waveform_sha256']
assert sha(P/'evidence/reference-terminal-balance.json')==base['source_report_sha256']
# Same PDK source set/corner and frozen device dimensions, not a cross-process fit.
result=json.loads((R/'scratch/transceiver-reference-bias-observation/result.json').read_text())
for name,h in ac['source_hashes_before'].items():
 if name in result['sources_before']:assert h==result['sources_before'][name]
derivatives={case['name']:case['samples'][0]['effective_charge_derivative_f'] for case in ac['cases']}
assert all(case['samples'][0]['frequency_hz']==1e6 for case in ac['cases'])
rows=[];summaries=[]
for rail,type_,node in [('xhigh','n','rbn'),('xlow','p','rbp')]:
 cd,cg=derivatives[type_+'d'],derivatives[type_+'g']
 original=next(r for r in base['results'] if r['rail']==rail)
 gates={(r['hold_ns'],r['bit'],r['window']):r for r in bias['biases'][node]['windows']}
 group=[]
 for row in original['rows']:
  gate=gates[row['hold_ns'],row['bit'],row['window']]
  predicted=cd*row['delta_v']+cg*gate['delta_v']
  item=dict(rail=rail,hold_ns=row['hold_ns'],bit=row['bit'],window=row['window'],
    observed_charge_c=row['observed_charge_c'],predicted_charge_c=predicted,
    error_c=predicted-row['observed_charge_c'],constant_fit_error_c=row['error_c'])
  rows.append(item);group.append(item)
 summaries.append(dict(rail=rail,drain_derivative_f=cd,gate_derivative_f=cg,
  maximum_error_c=max(abs(r['error_c']) for r in group),
  rms_error_c=float(np.sqrt(np.mean([r['error_c']**2 for r in group]))),
  maximum_constant_fit_error_c=max(abs(r['constant_fit_error_c']) for r in group)))
report=dict(coefficients_fitted_to_transient=False,summaries=summaries,rows=rows,
 source_hashes={p.name:sha(p) for p in (Path(__file__),ac_path,base_path,bias_path)},
 limitations=['Independent AC stimulus, but same PDK model; agreement is not silicon validation.',
 'Measured drain and gate voltages remain inputs; bias/rail dynamics are not predicted.',
 'Nominal DC derivatives are applied to finite voltage changes; nonlinear charge variation is omitted.',
 'Does not alter the already frozen independent-amplitude validation comparators.'])
(P/'evidence/reference-ac-charge-prediction.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
for row in summaries:print(row)
