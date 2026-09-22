"""Short source-representation discriminator; no reference circuit changes."""
import hashlib,json,re,subprocess
from pathlib import Path
import numpy as np
B=Path('/baseline');O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((B/'manifest.json').read_text());assert sha(B/'load.spice')==m['deck_sha256'] and sha(B/'demand.spice')==m['demand_sha256']
before={}
for path,h in m['source_sha256_before'].items():
 p=Path('/origin/frames.spice') if path=='/baseline/frames.spice' else Path(path)
 assert sha(p)==h;before[str(p)]=h
for p in [B/'load.spice',B/'demand.spice',Path(__file__)]:before[str(p)]=sha(p)
raw=(B/'demand.spice').read_text();series={}
for rail,body in re.findall(r'ILOAD([HL]) V[HL] 0 PWL\((.*?)\)',raw,re.S):
 numbers=re.findall(r'-?\d+\.\d+e[+-]\d+',body);series[rail]=np.array(list(map(float,numbers))).reshape(-1,2)
assert set(series)=={'H','L'}
rows=[]
for case in ['recorded','dc','startup1ps']:
 parts=[];errors={}
 for rail,a in series.items():
  if case=='dc':parts.append(f'ILOAD{rail} V{rail} 0 {a[0,1]:.17e}');continue
  if case=='startup1ps':
   y=float(np.interp(1e-12,a[:,0],a[:,1]));b=np.vstack([a[0],[1e-12,y],a[a[:,0]>1e-12]])
   sample=np.unique(np.r_[a[a[:,0]<=1e-12,0],1e-12]);errors[rail]=float(abs(np.interp(sample,a[:,0],a[:,1])-np.interp(sample,b[:,0],b[:,1])).max())
  else:b=a
  parts.append(f'ILOAD{rail} V{rail} 0 PWL(\n'+'\n'.join('+ '+' '.join(f'{x:.17e} {y:.17e}' for x,y in b[i:i+4]) for i in range(0,len(b),4))+'\n+ )')
 source='\n'.join(parts)+'\n';sp=O/(case+'-demand.spice');sp.write_text(source)
 base=(B/'load.spice').read_text();d=base.replace('.include /baseline/demand.spice',f'.include /work/{case}-demand.spice').replace('tran 5p 209.9n 0 5p','tran 5p 1n 0 5p').replace('/work/load.dat',f'/work/{case}.dat')
 p=O/(case+'.spice');p.write_text(d)
 with (O/(case+'.log')).open('w') as log:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=60)
 rows.append(dict(case=case,returncode=r.returncode,startup_max_current_change_a=errors,source_sha256=sha(sp),artifacts_sha256={e:sha(O/(case+e)) for e in ('.spice','.log','.dat') if (O/(case+e)).exists()}))
after={p:sha(Path(p)) for p in before};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n');print([(r['case'],r['returncode']) for r in rows])
