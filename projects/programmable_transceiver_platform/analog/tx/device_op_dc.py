"""Observation-only DC sweep: actual DAC tails and conducting mixer fingers."""
import hashlib,json,subprocess,time
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((B/'result.json').read_text());sources=[Path(p) for p in base['source_sha256_before']]
before={str(p):sha(p) for p in sources};assert before==base['source_sha256_before']
tails=[f'xd.xcl{i}.xtail' for i in range(4)]+[f'xd.xch{i}.xtail' for i in range(1,16)]
switches=['xm.xp.xp0','xm.xp.xp1','xm.xn.xn0','xm.xn.xn1']
params=['vds','vdsat','vgs','vth','id']
vectors=[f'@m.{dev}.m0[{param}]' for dev in tails+switches for param in params]
rows=[]
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,tails=tails,switches=switches,params=params,vectors=vectors,scope='Observation-only: save device parameters through the existing DC sweep, identical electrical deck.'),indent=2)+'\n')
for c in base['cases']:
 name=c['name'];src=B/(name+'.spice');assert sha(src)==c['artifacts_sha256']['.spice']
 d=src.read_text().replace('dc VCODE 0 255 1','save all '+' '.join(vectors)+'\ndc VCODE 0 255 1').replace('.endc','wrdata /work/'+name+'_devices.dat '+' '.join(vectors)+'\n.endc')
 p=O/(name+'.spice');p.write_text(d);pre=sha(p);start=time.monotonic()
 with (O/(name+'.log')).open('w') as f:r=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=180)
 assert sha(p)==pre
 files=[name+s for s in ('.spice','.log','.dat')]+[name+'_devices.dat']
 rows.append(dict(name=name,returncode=r.returncode,elapsed_seconds=time.monotonic()-start,baseline_deck_sha256=sha(src),deck_sha256_before=pre,artifacts_sha256={n:sha(O/n) for n in files if (O/n).exists()}));print(name,r.returncode,flush=True)
after={str(p):sha(p) for p in sources};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n')
