"""Clamped-control endpoints for FET-follower steering pump; no capture claim."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());assert r['returncode']==0 and not r['timed_out']
src=B/'follower.spice';assert sha(src)==r['artifacts_sha256']['.spice'];base=src.read_text()
before={p:sha(Path(p)) for p in r['source_sha256_before']};assert before==r['source_sha256_before']==r['source_sha256_after']
before[str(Path(__file__))]=sha(Path(__file__))
# Endpoint conditions span sampled split-ring frequencies around the target,
# with both phase signs; not guaranteed process/capture bounds.
rows=[]
(O/'manifest.json').write_text(json.dumps(dict(baseline_deck_sha256=sha(src),source_sha256_before=before,scope='CTRL clamp and associated precharges change together; FB delay sets signed phase. Actual follower retained; no cold-start or autonomous loop.'),indent=2)+'\n')
for control in (.98,1.16):
 for phase,delay in (('early','99.7n'),('late','100.3n')):
  name=f'v{control:g}_{phase}'
  changes={'VCLAMP CTRL 0 1.08':f'VCLAMP CTRL 0 {control:g}', '.ic v(CTRL)=1.08 v(XFILT.Z)=1.08':f'.ic v(CTRL)={control:g} v(XFILT.Z)={control:g}', '.ic v(DUMMY)=1.08':f'.ic v(DUMMY)={control:g}', 'VFB FB 0 PULSE(0 3.3 99.999n':f'VFB FB 0 PULSE(0 3.3 {delay}'}
  d=base
  for old,new in changes.items():assert d.count(old)==1;d=d.replace(old,new)
  d=d.replace('/work/follower.dat',f'/work/{name}.dat');p=O/(name+'.spice');p.write_text(d);h=sha(p)
  with (O/(name+'.log')).open('w') as log:
   try:s=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=360);code=s.returncode;timeout=False
   except subprocess.TimeoutExpired:code=None;timeout=True
  assert sha(p)==h
  rows.append(dict(name=name,control_v=control,phase=phase,delay=delay,changes=changes,returncode=code,timed_out=timeout,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.log','.dat') if (O/(name+e)).exists()}))
  (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,code,timeout,flush=True)
after={p:sha(Path(p)) for p in before};assert before==after
(O/'result.json').write_text(json.dumps(dict(source_sha256_before=before,source_sha256_after=after,cases=rows),indent=2)+'\n')
