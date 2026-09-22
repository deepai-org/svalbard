"""Measured ring-output replay with actual AC coupling/self-bias and injected current."""
import hashlib,json,subprocess,time,sys
recovery="--recovery" in sys.argv
from pathlib import Path
import numpy as np
O=Path('/work');B=Path('/baseline');M=Path('/measured')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((B/'result.json').read_text());bc=next(c for c in base['cases'] if c['name']=='nmos_c255');src=B/'nmos_c255.spice';assert sha(src)==bc['artifacts_sha256']['.spice']
measured=json.loads((M/'result.json').read_text());wave=M/'settling.dat';assert measured['returncode']==0 and sha(wave)==measured['artifacts_sha256']['.dat']
sources=[Path(p) for p in base['source_sha256_before']];before={str(p):sha(p) for p in sources};assert before==base['source_sha256_before']
with wave.open() as f:h=f.readline().lower().split()
a=np.loadtxt(wave,skiprows=1);assert np.all(np.diff(a[:,0])>0)
start=540e-9 if recovery else 590e-9;stop=600e-9;t=np.r_[start,a[(a[:,0]>start)&(a[:,0]<stop),0],stop]
d=src.read_text();replacements=[]
for name,node,col,old in [('VLO','LOIN','v(cp)','PULSE(0 3.3 1n 20p 20p 180p 400p)'),('VLOB','LOBIN','v(cn)','PULSE(3.3 0 1n 20p 20p 180p 400p)')]:
 vals=np.interp(t,a[:,0],a[:,h.index(col)]);line=f'{name} {node} 0 '+old+'\n';assert d.count(line)==1
 replacement=f'{name} {node} 0 PWL('+' '.join(f'{tt-start:.17g} {vv:.17g}' for tt,vv in zip(t,vals))+')\n';d=d.replace(line,replacement);replacements.append(dict(old=line,new=replacement))
d=d.replace('VLO LOIN 0 PWL','VLO RAWP 0 PWL').replace('VLOB LOBIN 0 PWL','VLOB RAWN 0 PWL')
add='CCP RAWP LOIN 200f\nCCN RAWN LOBIN 200f\nRFBP LOIN XLP.MID 100k\nRFBN LOBIN XLN.MID 100k\n'
d=d.replace('.control',add+'.control');rows=[]
if recovery:
 d=d.replace('tran 2p 10n 0 2p','tran 2p 60n 0 2p')
 d='\n'.join(l+' v(XLP.MID) v(XLN.MID)' if l.startswith(('save ','wrdata ')) else l for l in d.splitlines())+'\n'
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(src),measured_wave_sha256=sha(wave),samples=len(t),recovery=recovery,measured_start_ns=540 if recovery else 590,scope='Recorded CP/CN replay with actual coupling/feedback, equal+/-3uA injected into both buffer inputs after2ns. OP-initialized DAC; not autonomous loading/startup.'),indent=2)+'\n')
for name,current in [('zero',0),('minus',-3e-6),('plus',3e-6)]:
 inj=f'IEP 0 LOIN PWL(0 0 2n 0 2.1n {current:.17g})\nIEN 0 LOBIN PWL(0 0 2n 0 2.1n {current:.17g})\n'
 if recovery:inj=inj.replace(f'{current:.17g})',f'{current:.17g} 20n {current:.17g} 20.1n 0)')
 case=d.replace('.control',inj+'.control').replace('/work/nmos_c255.dat',f'/work/{name}.dat')
 p=O/(name+'.spice');p.write_text(case);pre=sha(p);start_time=time.monotonic()
 with (O/(name+'.log')).open('w') as f:
  try:r=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=900);rc=r.returncode;timeout=False
  except subprocess.TimeoutExpired:rc=None;timeout=True
 assert sha(p)==pre
 rows.append(dict(name=name,injection_a=current,returncode=rc,timed_out=timeout,deck_sha256_before=pre,elapsed_seconds=time.monotonic()-start_time,artifacts_sha256={ext:sha(O/(name+ext)) for ext in ('.spice','.log','.dat') if (O/(name+ext)).exists()}));print(name,rc,flush=True)
after={str(p):sha(p) for p in sources};assert before==after and sha(wave)==measured['artifacts_sha256']['.dat']
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n')
