"""Independent common-mode and differential-swing transformations of recorded clocks."""
import hashlib,json,re,subprocess,time
from pathlib import Path
import numpy as np
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((B/'result.json').read_text());src=B/'replay.spice';assert sha(src)==base['artifacts_sha256']['.spice'];before={p:sha(Path(p)) for p in base['source_sha256_before']};assert before==base['source_sha256_before']
original=src.read_text();matches=[re.search('^'+name+r' '+node+r' 0 PWL\(([^\n]+)\)$',original,re.M) for name,node in [('VLO','LOIN'),('VLOB','LOBIN')]]
a=[np.array([float(x) for x in match.group(1).split()]).reshape(-1,2) for match in matches];assert np.array_equal(a[0][:,0],a[1][:,0]);t=a[0][:,0];cm=(a[0][:,1]+a[1][:,1])/2;diff=(a[0][:,1]-a[1][:,1])/2
cases=[('cm_minus',-.15,1),('cm_plus',.15,1),('swing_low',0,.75),('swing_high',0,1.25)];rows=[]
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(src),planned_cases=cases,scope='Stiff-source diagnostic; retain instantaneous common-mode waveform while scaling differential swing, or shift common mode equally by+/-150mV.'),indent=2)+'\n')
for name,offset,scale in cases:
 d=original
 for idx,match in enumerate(matches):
  values=cm+offset+(1 if idx==0 else -1)*scale*diff
  prefix='VLO LOIN' if idx==0 else 'VLOB LOBIN';new=prefix+' 0 PWL('+' '.join(f'{tt:.17g} {vv:.17g}' for tt,vv in zip(t,values))+')';d=d.replace(match.group(0),new)
 d=d.replace('/work/replay.dat',f'/work/{name}.dat');p=O/(name+'.spice');p.write_text(d);pre=sha(p);start=time.monotonic()
 with (O/(name+'.log')).open('w') as f:
  try:r=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=300);rc=r.returncode;timeout=False
  except subprocess.TimeoutExpired:rc=None;timeout=True
 assert sha(p)==pre
 rows.append(dict(name=name,offset_v=offset,differential_scale=scale,returncode=rc,timed_out=timeout,elapsed_seconds=time.monotonic()-start,deck_sha256_before=pre,artifacts_sha256={ext:sha(O/(name+ext)) for ext in ('.spice','.log','.dat') if (O/(name+ext)).exists()}));print(name,rc,flush=True)
after={p:sha(Path(p)) for p in before};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n')
