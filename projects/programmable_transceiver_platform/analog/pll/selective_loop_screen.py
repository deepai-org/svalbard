"""Observe only exported vectors; circuit and solver unchanged."""
import argparse,hashlib,json,subprocess
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--short',action='store_true');ap.add_argument("--all-control",action="store_true");args=ap.parse_args()
O=Path('/work');B=Path('/prepared');K=Path('/killed')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
m=json.loads((B/'manifest.json').read_text());assert sha(B/'latest.spice')==m['deck_sha256']
r=json.loads((K/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after'] and sha(K/'latest.spice')==m['parent_deck_sha256']
before={}
for name,h in r['source_sha256_before'].items():
 p=Path('/original/latest.spice') if name=='/baseline/latest.spice' else Path(name)
 assert sha(p)==h;before[str(p)]=h
before[str(Path(__file__))]=sha(Path(__file__))
d=(B/'latest.spice').read_text();old=(K/'latest.spice').read_text();save=next(x for x in old.splitlines() if x.startswith('save '));selected=next(x for x in d.splitlines() if x.startswith('save '));assert d.replace(selected,save)==old
if args.all_control:
 assert args.short
 d=d.replace(selected,save)
if args.short:d=d.replace('tran 2p 8001n 0 2p uic','tran 2p 10n 0 2p uic')
p=O/'latest.spice';p.write_text(d);h=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(deck_sha256=h,source_sha256_before=before,parent_sha256=m['deck_sha256'],requested_horizon_ns=10 if args.short else 8001,exported_vectors=m['saved_vectors'],save_mode="all_control" if args.all_control else "selective"),indent=2)+'\n')
with (O/'latest.log').open('w') as log:
 try:q=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=180 if args.short else 14400);code=q.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
after={n:sha(Path(n)) for n in before};assert before==after and sha(p)==h
(O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={e:sha(O/('latest'+e)) for e in ('.spice','.log','.dat') if (O/('latest'+e)).exists()}),indent=2)+'\n');print(code,timeout)
