"""Actual DAC gate-load startup with static LO; compare UIC with operating point."""
import hashlib,json,subprocess,time
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((B/'result.json').read_text());c=next(c for c in base['cases'] if c['name']=='ideal_uic');src=B/'ideal_uic.spice';assert sha(src)==c['artifacts_sha256']['.spice']
before={p:sha(Path(p)) for p in c['source_sha256_before']};assert before==c['source_sha256_before'];rows=[]
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(src),scope='Actual loaded DAC and buffers retained; LO held static high/low.1us20ps maxstep with/without UIC. Ideal20uA bias and instantaneous supply.'),indent=2)+'\n')
for name,uic in [('op',''),('uic',' uic')]:
 d=src.read_text().replace('VLO LOIN 0 PULSE(0 3.3 1n 20p 20p 180p 400p)','VLO LOIN 0 3.3').replace('VLOB LOBIN 0 PULSE(3.3 0 1n 20p 20p 180p 400p)','VLOB LOBIN 0 0').replace('tran 2p 40n 0 2p uic',f'tran 20p 1u 0 20p{uic}').replace('/work/ideal_uic.dat',f'/work/{name}.dat')
 p=O/(name+'.spice');p.write_text(d);pre=sha(p);start=time.monotonic()
 with (O/(name+'.log')).open('w') as f:
  try:r=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=300);rc=r.returncode;timeout=False
  except subprocess.TimeoutExpired:rc=None;timeout=True
 assert sha(p)==pre
 rows.append(dict(name=name,returncode=rc,timed_out=timeout,deck_sha256_before=pre,elapsed_seconds=time.monotonic()-start,artifacts_sha256={ext:sha(O/(name+ext)) for ext in ('.spice','.log','.dat') if (O/(name+ext)).exists()}));print(name,rc,flush=True)
after={p:sha(Path(p)) for p in before};assert before==after
(O/'result.json').write_text(json.dumps(dict(source_sha256_before=before,source_sha256_after=after,cases=rows),indent=2)+'\n')
