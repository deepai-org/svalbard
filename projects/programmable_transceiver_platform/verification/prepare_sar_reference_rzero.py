"""Prepare resistor-only compensation intervention in intact three-frame SAR."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';O=R/'scratch/transceiver-sar-reference-rzero-prepared';D=R/'scratch/transceiver-adc-sar8-reference-reservoir'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
e=P/'evidence/adc-sar8-reference-reservoir-screen.json';case=next(c for c in json.loads(e.read_text())['cases'] if c['name']=='typical_first1')
for ext in ('.spice','.dat'):assert sha(D/('typical_first1'+ext))==case['artifacts_sha256'][ext]
s=(D/'typical_first1.spice').read_text();assert 'tran 5p 209.9n 0 5p' in s
pair=(P/'analog/reference/adc_reference_pair.spice').read_text()
changed=pair
for kind in ('scaled','complement'):
 changed=changed.replace(f'buffer_{kind}.spice',f'buffer_{kind}_tune.spice').replace(f'pt_reference_buffer_{kind} S=4',f'pt_reference_buffer_{kind}_tune S=4 CC=1p RZ=2000')
needle='.include /screen/reference/adc_reference_pair.spice';assert s.count(needle)==1
candidate=s.replace(needle,changed.rstrip()).replace('/work/typical_first1.dat','/work/baseline.dat')
assert candidate.replace(changed.rstrip(),needle).replace('/work/baseline.dat','/work/typical_first1.dat')==s
O.mkdir();(O/'baseline.spice').write_text(candidate)
m=dict(candidate='Only compensation zero resistor changes100/S to2000/S; original CC=1p, S=4 and2048-unit reservoirs.',donor_artifacts_sha256=case['artifacts_sha256'],source_evidence_sha256=sha(e),artifacts_sha256={'baseline.spice':sha(O/'baseline.spice')},qualification_plan=['Verify unchanged sources and exact donor reversal.','Compare all 24 decisions, final codes, reference errors and late small-residue behavior.','Compare bit1 span and ideal transfer error; no expectation of short-candidate reproduction.'],limitations=['Nominal process and prebiased initial state only.','Original ideal external clocks, targets and bias remain; this does not establish autonomous sample rate.','No production adoption or complete ADC accuracy claim.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(O)
