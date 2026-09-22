"""Prepare a different-amplitude validation fixture before inspecting its output."""
import hashlib,json,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
B=R/'scratch/transceiver-reference-bias-observation-prepared'
O=R/'scratch/transceiver-reference-charge-validation-prepared'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((B/'manifest.json').read_text())
for name,h in m['artifacts_sha256'].items():assert sha(B/name)==h
source=(B/'baseline.spice').read_text();candidate=source;changes={}
for prefix in ('VIP SP 0 PWL(', 'VIN SN 0 PWL('):
 line=next(l for l in source.splitlines() if l.startswith(prefix))
 assert '1.45' in line and '1.85' in line
 replacement=line.replace('1.45','1.60').replace('1.85','1.70')
 changes[line]=replacement;candidate=candidate.replace(line,replacement)
reverse=candidate
for old,new in changes.items():reverse=reverse.replace(new,old)
assert reverse==source
fitpath=P/'evidence/reference-load-charge-fit.json';fit=json.loads(fitpath.read_text())
assert len(fit['results'])==2 and all(r['training_hold_ns']==70 for r in fit['results'])
O.mkdir()
for name in m['artifacts_sha256']:
 if name!='baseline.spice':shutil.copyfile(B/name,O/name)
(O/'baseline.spice').write_text(candidate)
m.update(candidate='Independent100mV differential amplitude charge-law validation.',
 parent_preparation_sha256=sha(B/'manifest.json'),stimulus_changes=changes,
 frozen_constant_fit_sha256=sha(fitpath),
 frozen_constant_capacitance_f={r['rail']:r['constant_capacitance_f'] for r in fit['results']},
 artifacts_sha256={p.name:sha(p) for p in O.iterdir()},
 execution_status='Prepared only: require accepted bias observation and frozen selected law before launch.',
 qualification_plan=['Verify only input amplitudes change from400mV to100mV differential; preserve1.65V common mode, time schedule, circuit, probes and1.25ps timestep.',
 'Freeze any two-terminal coefficients from the existing large-amplitude data before executing this fixture.',
 'Score every new preclock/switching charge window with frozen parameters; report all errors, no refit.',
 'Validate full terminal KCL and code history; this different waveform cannot inherit exact-vector reproduction against the old stimulus.'],
 limitations=['Different amplitude changes code history but does not cover all inputs or bias conditions.',
 'Even successful endpoint charge prediction is not autonomous rail/code prediction.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(O)
