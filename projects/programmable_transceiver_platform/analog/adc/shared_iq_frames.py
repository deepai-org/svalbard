"""Extend verified simultaneous ADC fixture to three complete frames."""
import hashlib,json,subprocess,time,sys
same_history="--same-history" in sys.argv
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((B/'result.json').read_text());assert base['returncode']==0;src=B/('frames.spice' if same_history else 'preflight.spice');assert sha(src)==base['artifacts_sha256']['.spice']
before={p:sha(Path(p)) for p in base['source_sha256_before']};assert before==base['source_sha256_before']
d=src.read_text()
if same_history:
 lines=d.splitlines()
 for primary,secondary,node in [('VIP','VQ_IP','Q_SP'),('VIN','VQ_IN','Q_SN')]:
  first=next(l for l in lines if l.startswith(primary+' '));old=next(l for l in lines if l.startswith(secondary+' '))
  new=secondary+' '+node+' 0 '+first.split(' ',3)[3];assert d.count(old)==1;d=d.replace(old,new)
else:d=d.replace('tran 5p 1n 0 5p','tran 5p 209.9n 0 5p').replace('/work/preflight.dat','/work/frames.dat')
p=O/'frames.spice';p.write_text(d);pre=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(src),deck_sha256_before=pre,same_history=same_history,scope='Same-history mode changes only Q input sources; default mode is horizon-only extension1ns to209.9ns; actual two channels, opposite histories, shared actual compensated reference/reservoir, ideal common clocks/supplies.'),indent=2)+'\n');start=time.monotonic()
with (O/'frames.log').open('w') as f:
 try:r=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=3600);rc=r.returncode;timeout=False
 except subprocess.TimeoutExpired:rc=None;timeout=True
after={p:sha(Path(p)) for p in before};assert before==after and sha(p)==pre
(O/'result.json').write_text(json.dumps(dict(returncode=rc,timed_out=timeout,elapsed_seconds=time.monotonic()-start,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={ext:sha(O/('frames'+ext)) for ext in ('.spice','.log','.dat') if (O/('frames'+ext)).exists()}),indent=2)+'\n');print(rc,flush=True)
