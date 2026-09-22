"""Test top-node loading hypothesis with explicit equal 60fF shunts."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
B=R/'scratch/transceiver-sar-bottom-plates-prepared';O=R/'scratch/transceiver-sar-known-load-prepared'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((B/'manifest.json').read_text());assert sha(B/'baseline.spice')==m['artifacts_sha256']['baseline.spice']
s=(B/'baseline.spice').read_text();addition='CLOADP HP 0 60f\nCLOADN HN 0 60f\n'
assert s.count('.control')==1
candidate=s.replace('.control',addition+'.control');assert candidate.replace(addition,'')==s
fit=P/'evidence/sar-top-load-fit.json';beta=json.loads(fit.read_text())['beta']
# Active nominal MIM model at 27C; typical and no Monte Carlo perturbation.
unit=(1.47e-3*25e-12+3.79e-10*20e-6)*(1+4.0604e-5*2-6.90e-8*4)
array=256*unit
O.mkdir();(O/'baseline.spice').write_text(candidate)
m.update(candidate='Controlled top-node load: 60fF shunt per held node; all bottom plates observed.',
    baseline_preparation_sha256=sha(B/'manifest.json'),artifacts_sha256={'baseline.spice':sha(O/'baseline.spice')},
    prediction_source_sha256=sha(fit),added_capacitance_f=60e-15,array_capacitance_f=array,
    predicted_beta=1/(1/beta+60e-15/array),
    qualification_plan=['Verify only two shunt capacitors added.','Require terminal full transient and provenance.',
      'Compare frozen predicted beta against all decisions without refitting.'],
    limitations=['Diagnostic perturbation, not proposed production fix.','Additional capacitance can change acquisition and switching histories; use measured anchors/bottom trajectories.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(m['predicted_beta'])
