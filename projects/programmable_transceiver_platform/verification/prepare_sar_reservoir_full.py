"""Extend the one-factor reservoir candidate to the original three-frame timing."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';O=R/'scratch/transceiver-sar-reservoir-full-prepared';D=R/'scratch/transceiver-adc-sar8-reference-reservoir'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
e=P/'evidence/adc-sar8-reference-reservoir-screen.json';case=next(c for c in json.loads(e.read_text())['cases'] if c['name']=='typical_first1')
for ext in ('.spice','.dat'):assert sha(D/('typical_first1'+ext))==case['artifacts_sha256'][ext]
s=(D/'typical_first1.spice').read_text();assert 'tran 5p 209.9n 0 5p' in s
extra='XHR_EXTRA VH 0 pt_ref_reservoir_2048\nXLR_EXTRA VL 0 pt_ref_reservoir_2048\n';needle='XLR VL 0 pt_ref_reservoir_2048\n';assert s.count(needle)==1
candidate=s.replace(needle,needle+extra).replace('/work/typical_first1.dat','/work/baseline.dat')
assert candidate.replace(extra,'').replace('/work/baseline.dat','/work/typical_first1.dat')==s
O.mkdir();(O/'baseline.spice').write_text(candidate)
m=dict(candidate='4096 units per rail, original three-frame 209.9ns timing and controller.',donor_artifacts_sha256=case['artifacts_sha256'],source_evidence_sha256=sha(e),artifacts_sha256={'baseline.spice':sha(O/'baseline.spice')},qualification_plan=['Verify unchanged sources and exact donor reversal.','Compare all 24 decisions, final codes, reference errors and late small-residue behavior.','Verify first 80ns matches the already completed short candidate within 10uV before combining evidence.'],limitations=['Nominal process and prebiased initial state only.','Original ideal external clocks, targets and bias remain; this does not establish autonomous sample rate.','No production adoption or complete ADC accuracy claim.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(O)
