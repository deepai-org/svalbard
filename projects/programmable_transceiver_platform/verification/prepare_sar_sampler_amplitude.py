"""Matched smaller-amplitude test for one/two sampler banks; same timing and common mode."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for banks,source in [(1,'sar-reference-clamped'),(2,'sar-sampler-double')]:
 B=R/('scratch/transceiver-'+source+'-prepared');O=R/f'scratch/transceiver-sar-amplitude-bank{banks}-prepared';m=json.loads((B/'manifest.json').read_text());assert sha(B/'baseline.spice')==m['artifacts_sha256']['baseline.spice']
 s=(B/'baseline.spice').read_text();changes=[];lines=s.splitlines()
 for i,l in enumerate(lines):
  if l.startswith(('VIP ','VIN ')):
   new=l.replace('1.45','1.60').replace('1.85','1.70');assert new!=l;changes.append([l,new]);lines[i]=new
 assert len(changes)==2
 candidate='\n'.join(lines)+'\n';restored=candidate
 for old,new in changes:restored=restored.replace(new,old)
 assert restored==s
 O.mkdir();(O/'baseline.spice').write_text(candidate)
 m.update(candidate=f'{banks} sampler bank(s), differential levels+0.1/-0.1/+0.1V, unchanged1.65V common mode and original timing.',amplitude_v=.1,banks=banks,baseline_preparation_sha256=sha(B/'manifest.json'),input_changes=changes,artifacts_sha256={'baseline.spice':sha(O/'baseline.spice')},qualification_plan=['Compare matched banks at all three final codes and sample-edge errors.','Nominal ideal-source codes115/140/115; no calibrated correction.'],limitations=['Ideal clocks and reference rails.','Two amplitudes across separate tests do not establish INL/DNL or ENOB.','No production adoption without physical references and clock loading.'])
 (O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');print(O)
