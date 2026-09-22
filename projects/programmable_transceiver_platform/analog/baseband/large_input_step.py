"""Matched actual filter step histories from verified DC transfer fixtures."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');name='cm1.177_fb20000'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=[]
for label in ('baseline','candidate'):
 B=Path('/'+label);r=json.loads((B/'result.json').read_text());assert r['sources_before']==r['sources_after'];before=dict(r['sources_before'])
 for n,h in before.items():assert sha(Path(n))==h,n
 before[str(Path(__file__))]=sha(Path(__file__))
 c=next(c for c in r['cases'] if c['name']==name);assert c['returncode']==0 and sha(B/(name+'.spice'))==c['artifacts_sha256']['.spice']
 original=(B/(name+'.spice')).read_text();pulse='VD D 0 PWL(0n 0 20n 0 20.1n .05 120n .05 120.1n -.05 220n -.05 220.1n 0)'
 assert original.count('VD D 0 0')==1
 d=original.replace('VD D 0 0',pulse).replace('dc VD -.4 .4 .005','tran 20p 300n 0 20p').replace(f'/work/{name}.dat',f'/work/{label}.dat')
 assert d.replace(pulse,'VD D 0 0').replace('tran 20p 300n 0 20p','dc VD -.4 .4 .005').replace(f'/work/{label}.dat',f'/work/{name}.dat')==original
 p=O/(label+'.spice');p.write_text(d);h=sha(p)
 with (O/(label+'.log')).open('w') as f:q=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=120)
 after={n:sha(Path(n)) for n in before};assert before==after and sha(p)==h
 rows.append(dict(name=label,parent_sha256=sha(B/(name+'.spice')),returncode=q.returncode,sources_before=before,sources_after=after,artifacts_sha256={e:sha(O/(label+e)) for e in ('.spice','.dat','.log') if (O/(label+e)).exists()}))
(O/'result.json').write_text(json.dumps(dict(cases=rows,pulse=pulse,horizon_ns=300,maxstep_ps=20),indent=2)+'\n');print([(x['name'],x['returncode']) for x in rows])
