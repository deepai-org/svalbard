"""Common-mode-only substitution in actual shared-reference dual ADC fixture."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());assert r['returncode']==0 and not r['timed_out'];src=B/'frames.spice';assert sha(src)==r['artifacts_sha256']['.spice']
before={p:sha(Path(p)) for p in r['source_sha256_before']};assert before==r['source_sha256_before']==r['source_sha256_after'];before[str(Path(__file__))]=sha(Path(__file__))
base=src.read_text();changes={}
for line in base.splitlines():
 if line.split(' ')[0] in ('VIP','VIN','VQ_IP','VQ_IN'):changes[line]=line.replace('1.85','1.27').replace('1.45','0.87')
assert len(changes)==4;d=base
for old,new in changes.items():assert d.count(old)==1;d=d.replace(old,new)
p=O/'frames.spice';p.write_text(d);h=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(baseline_deck_sha256=sha(src),source_sha256_before=before,changes=changes,deck_sha256_before=h,scope='Four input-source common modes1.65->1.07V; differential swing remains+/-0.4V. Actual sample drivers/CDAC/control/shared reference retained, ideal source impedance/clocks remain.'),indent=2)+'\n')
with (O/'frames.log').open('w') as log:
 try:s=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=900);code=s.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
after={p:sha(Path(p)) for p in before};assert before==after and sha(p)==h
(O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={e:sha(O/('frames'+e)) for e in ('.spice','.log','.dat') if (O/('frames'+e)).exists()}),indent=2)+'\n');print(code,timeout)
