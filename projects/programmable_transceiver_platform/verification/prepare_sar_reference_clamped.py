"""Prepare ideal-rail diagnostic with otherwise unchanged full SAR."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';O=R/'scratch/transceiver-sar-reference-clamped-prepared';D=R/'scratch/transceiver-adc-sar8-reference-reservoir'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
e=P/'evidence/adc-sar8-reference-reservoir-screen.json';case=next(c for c in json.loads(e.read_text())['cases'] if c['name']=='typical_first1')
for ext in ('.spice','.dat'):assert sha(D/('typical_first1'+ext))==case['artifacts_sha256'][ext]
s=(D/'typical_first1.spice').read_text();assert 'tran 5p 209.9n 0 5p' in s
extra='VCLH VH 0 2.15\nVCLL VL 0 1.15\n'
assert s.count('.control')==1
candidate=s.replace('.control',extra+'.control').replace('/work/typical_first1.dat','/work/baseline.dat')
assert candidate.replace(extra,'').replace('/work/baseline.dat','/work/typical_first1.dat')==s
O.mkdir();(O/'baseline.spice').write_text(candidate)
m=dict(candidate='Ideal voltage sources clamp VH=2.15 and VL=1.15; physical drivers remain connected, all other circuit elements and clocks retained.',donor_artifacts_sha256=case['artifacts_sha256'],source_evidence_sha256=sha(e),artifacts_sha256={'baseline.spice':sha(O/'baseline.spice')},qualification_plan=['Verify unchanged sources and exact donor reversal.','Compare all 24 decisions, final codes, reference errors and late small-residue behavior.','Compare full code and residue trajectories to determine remaining non-reference error. Ideal clamp is diagnostic only, not realizable regulation or a rigorous best-case accuracy bound.'],limitations=['Nominal process and prebiased initial state only.','Original ideal external clocks, targets and bias remain; this does not establish autonomous sample rate.','No production adoption or complete ADC accuracy claim.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(O)
