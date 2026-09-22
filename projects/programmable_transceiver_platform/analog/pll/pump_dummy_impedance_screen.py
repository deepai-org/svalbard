"""Finite dummy-source resistance with/without explicit MIM reservoir; diagnostic."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());case=next(c for c in r['cases'] if c['name']=='steering');assert case['returncode']==0 and not case['timed_out']
src=B/'steering.spice';assert sha(src)==case['artifacts_sha256']['.spice']
before={p:sha(Path(p)) for p in r['source_sha256_before']};assert before==r['source_sha256_before']==r['source_sha256_after']
reservoir=Path('/screen/reference/reservoir_mim.spice');before[str(reservoir)]=sha(reservoir)
base=src.read_text();assert base.count('VDUMMY DUMMY 0 1.08')==1
rows=[]
for name in ('resistive','reservoir'):
 d=base.replace('VDUMMY DUMMY 0 1.08','VDUMMY DDRIVE 0 1.08\nRDUMMY DDRIVE DUMMY 1k').replace('/work/steering.dat',f'/work/{name}.dat')
 if name=='reservoir':
  d=d.replace('.control','.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical\n.include /screen/reference/reservoir_mim.spice\nXDC DUMMY 0 pt_ref_reservoir_32\n.ic v(DUMMY)=1.08\n.control')
 p=O/(name+'.spice');p.write_text(d);h=sha(p)
 (O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(src),scope='1kohm dummy source; optional32-unit MIM reservoir precharged1.08V, not cold startup or real bias generator.'),indent=2)+'\n')
 with (O/(name+'.log')).open('w') as log:
  try:s=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=300);code=s.returncode;timeout=False
  except subprocess.TimeoutExpired:code=None;timeout=True
 assert sha(p)==h
 rows.append(dict(name=name,returncode=code,timed_out=timeout,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.log','.dat') if (O/(name+e)).exists()}))
 (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,code,timeout,flush=True)
after={p:sha(Path(p)) for p in before};assert after==before
(O/'result.json').write_text(json.dumps(dict(source_sha256_before=before,source_sha256_after=after,cases=rows),indent=2)+'\n')
