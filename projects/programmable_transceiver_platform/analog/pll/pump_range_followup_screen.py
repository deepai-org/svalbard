"""Execute prepared range follow-ups without changing the active endpoint runner."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');D=Path('/prepared')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());assert r['returncode']==0 and not r['timed_out']
m=json.loads((D/'manifest.json').read_text());assert sha(B/'follower.spice')==m['baseline_sha256']==r['artifacts_sha256']['.spice']
before={p:sha(Path(p)) for p in r['source_sha256_before']};assert before==r['source_sha256_before']==r['source_sha256_after']
for p in [Path(__file__),D/'manifest.json']+list(D.glob('*.spice')):before[str(p)]=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(baseline_deck_sha256=m['baseline_sha256'],source_sha256_before=before,preparation=m),indent=2)+'\n')
rows=[]
for c in m['cases']:
 n=c['name'];src=D/(n+'.spice');assert sha(src)==c['deck_sha256'];d=src.read_text();rev=d
 for old,new in c['changes'].items():assert rev.count(new)==1;rev=rev.replace(new,old)
 assert rev==(B/'follower.spice').read_text()
 p=O/(n+'.spice');p.write_text(d)
 with (O/(n+'.log')).open('w') as log:
  try:s=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=360);code=s.returncode;timeout=False
  except subprocess.TimeoutExpired:code=None;timeout=True
 assert sha(p)==c['deck_sha256']
 rows.append(dict(c,returncode=code,timed_out=timeout,artifacts_sha256={e:sha(O/(n+e)) for e in ('.spice','.log','.dat') if (O/(n+e)).exists()}))
 (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(n,code,timeout,flush=True)
after={p:sha(Path(p)) for p in before};assert before==after
(O/'result.json').write_text(json.dumps(dict(source_sha256_before=before,source_sha256_after=after,cases=rows),indent=2)+'\n')
