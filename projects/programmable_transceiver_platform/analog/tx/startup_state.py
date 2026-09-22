"""Separate ideal-clock UIC replay from observation-only ring replay."""
import hashlib,json,subprocess,time
from pathlib import Path
O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
extra='v(CODE) v(BN) '+' '.join(f'v(D{i})' for i in range(8))+' v(XD.L0) v(XD.L0B) v(XD.H1) v(XD.H1B) v(XD.H15) v(XD.H15B) v(XD.XCL0.T) v(XD.XCH1.T)'
rows=[]
for name,folder in [('ideal_uic','/ideal'),('ring_probe','/ring')]:
 B=Path(folder);old=json.loads((B/'result.json').read_text());bc=next(c for c in old['cases'] if c['name']=='nmos_c255');src=B/'nmos_c255.spice';assert sha(src)==bc['artifacts_sha256']['.spice']
 before={p:sha(Path(p)) for p in old['source_sha256_before']};assert before==old['source_sha256_before']
 d=src.read_text().replace('/work/nmos_c255.dat',f'/work/{name}.dat')
 if name=='ideal_uic':d=d.replace('tran 2p 10n 0 2p','tran 2p 40n 0 2p uic')
 d='\n'.join(l+' '+extra if l.startswith(('save ','wrdata ')) else l for l in d.splitlines())+'\n'
 p=O/(name+'.spice');p.write_text(d);pre=sha(p)
 (O/(name+'_manifest.json')).write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(src),deck_sha256_before=pre,extra_vectors=extra),indent=2)+'\n');start=time.monotonic()
 with (O/(name+'.log')).open('w') as f:
  try:r=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=300);rc=r.returncode;timeout=False
  except subprocess.TimeoutExpired:rc=None;timeout=True
 after={p:sha(Path(p)) for p in before};assert before==after and sha(p)==pre
 rows.append(dict(name=name,returncode=rc,timed_out=timeout,elapsed_seconds=time.monotonic()-start,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={ext:sha(O/(name+ext)) for ext in ('.spice','.log','.dat') if (O/(name+ext)).exists()}));print(name,rc,flush=True)
(O/'result.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n')
