"""Require accepted observations and freeze model parameters before validation."""
import argparse,contextlib,hashlib,io,json,runpy
from pathlib import Path
HERE=Path(__file__).resolve().parent;P=HERE.parent;R=P.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
ap=argparse.ArgumentParser();ap.add_argument('--check-only',action='store_true');args=ap.parse_args()
B=R/'scratch/transceiver-reference-charge-validation-prepared'
PB=R/'scratch/transceiver-reference-bias-observation-prepared'
m=json.loads((B/'manifest.json').read_text())
assert sha(PB/'manifest.json')==m['parent_preparation_sha256']
for name,h in m['artifacts_sha256'].items():assert sha(B/name)==h
s=(B/'baseline.spice').read_text()
for old,new in m['stimulus_changes'].items():
 assert s.count(new)==1;s=s.replace(new,old)
assert s==(PB/'baseline.spice').read_text()
for name in m['artifacts_sha256']:
 if name!='baseline.spice':assert sha(B/name)==sha(PB/name)
constant_path=P/'evidence/reference-load-charge-fit.json'
assert sha(constant_path)==m['frozen_constant_fit_sha256']
with contextlib.redirect_stdout(io.StringIO()):
 state=runpy.run_path(str(HERE/'check_reference_bias_observation.py'))
if 'report' not in state or not state['report']['reproduction_pass']:
 print('Validation scope checks pass; accepted bias observations pending. Launch not authorized by this gate.')
 raise SystemExit(0 if args.check_only else 1)
model_path=P/'evidence/reference-two-terminal-charge.json'
if not model_path.exists():
 print('Accepted observations available; two-terminal training report must be generated before launch.')
 raise SystemExit(0 if args.check_only else 1)
model=json.loads(model_path.read_text())
for name,h in model['source_hashes'].items():
 path=(P/'system_model'/name) if name.endswith('.py') else (P/'evidence'/name)
 assert sha(path)==h
models=[]
for row in model['results']:
 item={k:v for k,v in row.items() if k not in ('rows','summaries')}
 # Preserve diagnostic status: negative/unidentifiable fits are not silently
 # converted to passive models or refit using the validation experiment.
 models.append(item)
frozen=dict(preparation_sha256=sha(B/'manifest.json'),
 constant_fit_sha256=sha(constant_path),two_terminal_fit_sha256=sha(model_path),
 bias_observation_sha256=sha(P/'evidence/reference-bias-observation.json'),
 constant_capacitance_f=m['frozen_constant_capacitance_f'],two_terminal_models=models,
 scoring='All24 preclock and24 switching windows per rail; no coefficient refit or window exclusion.',
 limitations=['No charge-error acceptance budget established; report prediction errors without declaring physical qualification.'])
if args.check_only:
 print('Scope, provenance and training checks pass; ready to freeze before launch.')
else:
 destination=P/'evidence/reference-charge-validation-frozen.json'
 encoded=json.dumps(frozen,indent=2,allow_nan=False)+'\n'
 if destination.exists():assert destination.read_text()==encoded,'Frozen validation model differs; do not overwrite'
 else:
  assert not (R/'scratch/transceiver-reference-charge-validation').exists(),'Validation must not precede coefficient freeze'
  with destination.open('x') as f:f.write(encoded)
 print(destination)
