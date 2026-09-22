"""Execute prepared observation-only reference current replay."""
import hashlib,json,subprocess
from pathlib import Path
B=Path('/baseline');O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((B/'manifest.json').read_text());assert m['exact_reversal_verified'] and sha(B/'frames.spice')==m['prepared_deck_sha256']
before=m['source_sha256_before'].copy()
for p,h in before.items():assert sha(Path(p))==h
before[str(Path(__file__))]=sha(Path(__file__));before[str(B/'frames.spice')]=sha(B/'frames.spice')
p=O/'frames.spice';p.write_text((B/'frames.spice').read_text());h=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(preparation=m,source_sha256_before=before,deck_sha256_before=h,voltage_reproduction_tolerance_v=1e-5,current_reproduction_tolerance_a=1e-8),indent=2)+'\n')
with (O/'frames.log').open('w') as log:
 try:run=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=900);code=run.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
after={p:sha(Path(p)) for p in before};assert before==after and sha(p)==h
(O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={e:sha(O/('frames'+e)) for e in ('.spice','.log','.dat') if (O/('frames'+e)).exists()}),indent=2)+'\n');print(code,timeout)
