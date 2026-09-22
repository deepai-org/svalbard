"""Matched worst observed major-carry case with halved transient timestep."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');name='c32_skew0.2';base=json.loads((B/'result.json').read_text());src=B/(name+'.spice')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(src)==next(c for c in base['cases'] if c['name']==name)['artifacts_sha256']['.spice']
before={path:sha(Path(path)) for path in base['source_sha256_after']};assert before==base['source_sha256_after']
d=src.read_text();assert d.count('tran 5p 79.9n 0 5p')==1;d=d.replace('tran 5p 79.9n 0 5p','tran 2.5p 79.9n 0 2.5p')
(O/(name+'.spice')).write_text(d);(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(src)),indent=2)+'\n')
with (O/(name+'.log')).open('w') as log:r=subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,timeout=300)
after={path:sha(Path(path)) for path in before};assert before==after
(O/'result.json').write_text(json.dumps(dict(name=name,returncode=r.returncode,baseline_deck_sha256=sha(src),source_sha256_before=before,source_sha256_after=after,artifacts_sha256={s:sha(O/(name+s)) for s in ('.spice','.dat','.log') if (O/(name+s)).exists()}),indent=2)+'\n');print('Fine-step simulator returned',r.returncode)
