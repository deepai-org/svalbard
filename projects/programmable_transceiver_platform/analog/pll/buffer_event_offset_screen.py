"""Shift electrically separate feedback pulse by +/-1ps; diagnostic only."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());original=(B/'buffer.spice').read_text();assert sha(B/'buffer.spice')==r['artifacts_sha256']['.spice']
before={p:sha(Path(p)) for p in r['source_sha256_before']};assert before==r['source_sha256_before']==r['source_sha256_after']
old='VFB FB 0 PULSE(0 3.3 100n 100p 100p 25.5n 51.2n)';assert original.count(old)==1
rows=[]
for name,delay in (('early','99.999n'),('late','100.001n')):
 d=original.replace(old,old.replace('100n',delay)).replace('/work/buffer.dat',f'/work/{name}.dat')
 p=O/(name+'.spice');p.write_text(d);h=sha(p)
 with (O/(name+'.log')).open('w') as log:
  try:s=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=300);code=s.returncode;timeout=False
  except subprocess.TimeoutExpired:code=None;timeout=True
 assert sha(p)==h
 rows.append(dict(name=name,delay=delay,returncode=code,timed_out=timeout,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.log','.dat') if (O/(name+e)).exists()}))
 (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,code,timeout,flush=True)
after={p:sha(Path(p)) for p in before};assert before==after
(O/'result.json').write_text(json.dumps(dict(baseline_deck_sha256=sha(B/'buffer.spice'),source_sha256_before=before,source_sha256_after=after,cases=rows),indent=2)+'\n')
