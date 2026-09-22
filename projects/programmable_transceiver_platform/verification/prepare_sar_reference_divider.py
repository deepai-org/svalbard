"""Prepare high-reference input common-mode attenuation experiment."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';O=R/'scratch/transceiver-sar-reference-divider-prepared';D=R/'scratch/transceiver-adc-sar8-reference-reservoir'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
e=P/'evidence/adc-sar8-reference-reservoir-screen.json';case=next(c for c in json.loads(e.read_text())['cases'] if c['name']=='typical_first1')
for ext in ('.spice','.dat'):assert sha(D/('typical_first1'+ext))==case['artifacts_sha256'][ext]
s=(D/'typical_first1.spice').read_text();assert 'tran 5p 209.9n 0 5p' in s
pair=(P/'analog/reference/adc_reference_pair.spice').read_text()
cell=(P/'analog/reference/buffer_complement.spice').read_text()
changed=cell.replace('XIP A OUT T','XIP A FBLOW T').replace('XIN X IN T','XIN X INLOW T')
needle='XIP A FBLOW T'
addition='RFIN IN INLOW 10k\nRFIG INLOW VSS 30k\nRFFB OUT FBLOW 10k\nRFFG FBLOW VSS 30k\n'
changed=changed.replace(needle,addition+needle)
assert changed.replace(addition,'').replace('XIP A FBLOW T','XIP A OUT T').replace('XIN X INLOW T','XIN X IN T')==cell
expanded=pair.replace('.include /screen/reference/buffer_complement.spice',changed.rstrip())
needle='.include /screen/reference/adc_reference_pair.spice';assert s.count(needle)==1
candidate=s.replace(needle,expanded.rstrip()).replace('/work/typical_first1.dat','/work/baseline.dat')
assert candidate.replace(expanded.rstrip(),needle).replace('/work/baseline.dat','/work/typical_first1.dat')==s
O.mkdir();(O/'baseline.spice').write_text(candidate)
m=dict(candidate='Matched10k/30k dividers lower both high-amplifier input voltages to0.75 nominal; original devices, reservoirs, compensation and clocks retained.',donor_artifacts_sha256=case['artifacts_sha256'],source_evidence_sha256=sha(e),artifacts_sha256={'baseline.spice':sha(O/'baseline.spice')},qualification_plan=['Verify unchanged sources and exact donor reversal.','Compare all 24 decisions, final codes, reference errors and late small-residue behavior.','Compare bit1 span, code accuracy and static regulation; divider noise/mismatch and finite target impedance remain unqualified.'],limitations=['Nominal process and prebiased initial state only.','Original ideal external clocks, targets and bias remain; this does not establish autonomous sample rate.','No production adoption or complete ADC accuracy claim.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(O)
