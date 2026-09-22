"""Extend the observed NMOS ring/TX startup without circuit changes."""
import hashlib,json,subprocess,time
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
old=json.loads((B/'result.json').read_text());c=next(c for c in old['cases'] if c['name']=='ring_probe');src=B/'ring_probe.spice';assert sha(src)==c['artifacts_sha256']['.spice']
before={p:sha(Path(p)) for p in c['source_sha256_before']};assert before==c['source_sha256_before']
d=src.read_text().replace('tran 2p 40n 0 2p uic','tran 2p 600n 0 2p uic').replace('/work/ring_probe.dat','/work/settling.dat');p=O/'settling.spice';p.write_text(d);pre=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(src),deck_sha256_before=pre,scope='Only extend40ns to600ns; identical seeded NMOS ring/TX circuit, UIC,2ps maxstep and observations.'),indent=2)+'\n');start=time.monotonic()
with (O/'settling.log').open('w') as f:
 try:r=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=1800);rc=r.returncode;timeout=False
 except subprocess.TimeoutExpired:rc=None;timeout=True
after={p:sha(Path(p)) for p in before};assert before==after and sha(p)==pre
(O/'result.json').write_text(json.dumps(dict(returncode=rc,timed_out=timeout,elapsed_seconds=time.monotonic()-start,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={ext:sha(O/('settling'+ext)) for ext in ('.spice','.log','.dat') if (O/('settling'+ext)).exists()}),indent=2)+'\n');print(rc,flush=True)
