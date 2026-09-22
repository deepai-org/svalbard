"""Diagnostic extra20ns track time, with original bit timing and ideal reference clamps."""
import hashlib,json,re
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-sar-reference-clamped-prepared';O=R/'scratch/transceiver-sar-long-acquisition-prepared'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((B/'manifest.json').read_text());assert sha(B/'baseline.spice')==m['artifacts_sha256']['baseline.spice']
e=P/'evidence/sar-reference-clamped.json';audit=json.loads(e.read_text());assert audit['completed'] and audit['clamps_verified']
s=(B/'baseline.spice').read_text();lines=s.splitlines();changes=[]
# Shift only control PWL times >=70ns, leaving input stimulus and analog circuitry intact.
controls={'VRST','VSTART','VUPDATE','VS','VSB','VC','VMASK'}
for i,line in enumerate(lines):
 if line.split() and line.split()[0] in controls:
  assert 'PWL(' in line
  new=re.sub(r'(?<![\w.])(\d+(?:\.\d+)?)n',lambda z:f'{float(z[1])+20:g}n' if float(z[1])>=70 else z[0],line)
  if new!=line:changes.append([line,new]);lines[i]=new
candidate='\n'.join(lines)+'\n';assert candidate.count('tran 5p 209.9n 0 5p')==1
candidate=candidate.replace('tran 5p 209.9n 0 5p','tran 5p 100n 0 5p')
restored=candidate.replace('tran 5p 100n 0 5p','tran 5p 209.9n 0 5p')
for old,new in changes:assert restored.count(new)==1;restored=restored.replace(new,old)
assert restored==s
O.mkdir();(O/'baseline.spice').write_text(candidate)
m.update(candidate='Acquisition diagnostic: first hold90ns rather than70ns, input change remains60ns, first clocks90.5/95.5ns; stop100ns.',baseline_preparation_sha256=sha(B/'manifest.json'),baseline_evidence_sha256=sha(e),control_changes=changes,artifacts_sha256={'baseline.spice':sha(O/'baseline.spice')},qualification_plan=['Verify exact control-only reversal and rail clamps.','Compare driver and held errors at hold edge90ns to original70ns; first two decisions only.'],limitations=['Extra track time is a diagnostic, not an acceptable sample-rate reduction.','Ideal rails; only first frame and two comparisons.','No full-conversion accuracy, noise or mismatch qualification.'])
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(O,len(changes),'control lines shifted')
