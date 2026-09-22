"""Replay measured buffer inputs with ideal voltage sources, not an oscillator substitute."""
import hashlib,json,subprocess,time
from pathlib import Path
import numpy as np
O=Path('/work');B=Path('/baseline');M=Path('/measured')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((B/'result.json').read_text());bc=next(c for c in base['cases'] if c['name']=='nmos_c255');src=B/'nmos_c255.spice';assert sha(src)==bc['artifacts_sha256']['.spice']
measured=json.loads((M/'result.json').read_text());wave=M/'settling.dat';assert measured['returncode']==0 and sha(wave)==measured['artifacts_sha256']['.dat']
sources=[Path(p) for p in base['source_sha256_before']];before={str(p):sha(p) for p in sources};assert before==base['source_sha256_before']
with wave.open() as f:h=f.readline().lower().split()
a=np.loadtxt(wave,skiprows=1);assert np.all(np.diff(a[:,0])>0)
start=590e-9;stop=600e-9;t=np.r_[start,a[(a[:,0]>start)&(a[:,0]<stop),0],stop]
d=src.read_text();replacements=[]
for name,node,col,old in [('VLO','LOIN','v(loin)','PULSE(0 3.3 1n 20p 20p 180p 400p)'),('VLOB','LOBIN','v(lobin)','PULSE(3.3 0 1n 20p 20p 180p 400p)')]:
 vals=np.interp(t,a[:,0],a[:,h.index(col)]);line=f'{name} {node} 0 '+old+'\n';assert d.count(line)==1
 replacement=f'{name} {node} 0 PWL('+' '.join(f'{tt-start:.17g} {vv:.17g}' for tt,vv in zip(t,vals))+')\n';d=d.replace(line,replacement);replacements.append(dict(old=line,new=replacement))
d=d.replace('/work/nmos_c255.dat','/work/replay.dat');p=O/'replay.spice';p.write_text(d);pre=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(src),measured_wave_sha256=sha(wave),deck_sha256_before=pre,samples=len(t),measured_window_ns=[590,600],scope='Measured LOIN/LOBIN replayed as stiff sources into unchanged OP-initialized NMOS TX; no feedback/loading equivalence asserted.'),indent=2)+'\n');start_time=time.monotonic()
with (O/'replay.log').open('w') as f:
 try:r=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=300);rc=r.returncode;timeout=False
 except subprocess.TimeoutExpired:rc=None;timeout=True
after={str(p):sha(p) for p in sources};assert before==after and sha(p)==pre and sha(wave)==measured['artifacts_sha256']['.dat']
(O/'result.json').write_text(json.dumps(dict(returncode=rc,timed_out=timeout,elapsed_seconds=time.monotonic()-start_time,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={ext:sha(O/('replay'+ext)) for ext in ('.spice','.log','.dat') if (O/('replay'+ext)).exists()}),indent=2)+'\n');print(rc,flush=True)
