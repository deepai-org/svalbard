"""Execute exact prepared reference-only recorded-current fixture."""
import hashlib,json,subprocess
from pathlib import Path
B=Path('/baseline');O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((B/'manifest.json').read_text());assert sha(B/'load.spice')==m['deck_sha256'] and sha(B/'demand.spice')==m['demand_sha256']
before={}
for path,h in m['source_sha256_before'].items():
 actual=Path('/origin/frames.spice') if path=='/baseline/frames.spice' else Path(path)
 assert sha(actual)==h;before[str(actual)]=h
for p in [B/'load.spice',B/'demand.spice',Path(__file__)]:before[str(p)]=sha(p)
p=O/'load.spice';p.write_text((B/'load.spice').read_text());h=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(preparation=m,source_sha256_before=before,deck_sha256_before=h,requested_horizon_ns=209.9,diagnostic_rail_difference_limit_v=.001),indent=2)+'\n')
with (O/'load.log').open('w') as log:
 try:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=900);code=r.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
after={p:sha(Path(p)) for p in before};assert before==after and sha(p)==h
(O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={e:sha(O/('load'+e)) for e in ('.spice','.log','.dat') if (O/('load'+e)).exists()}),indent=2)+'\n');print(code,timeout)
