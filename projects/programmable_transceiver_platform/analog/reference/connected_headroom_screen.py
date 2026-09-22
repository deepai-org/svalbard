"""Observation-only device diagnostic for the connected compensated ADC reference."""
import hashlib,json,subprocess,sys
shared_iq="--shared-iq" in sys.argv
from pathlib import Path
O=Path('/work');B=Path('/baseline');src=B/('frames.spice' if shared_iq else 'typical_first-1.spice');base=json.loads((B/'result.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
record=base if shared_iq else next(c for c in base['cases'] if c['name']=='typical_first-1')
assert sha(src)==record['artifacts_sha256']['.spice']
wave_name='frames.dat' if shared_iq else 'typical_first-1.dat'
sources=[Path(p) for p in base['source_sha256_before']];before={str(p):sha(p) for p in sources}
probes=[f'v(XREF.{rail}.{node})' for rail in ('XHIGH','XLOW') for node in ('A','T','X','Z')]
probes += [f'@m.xref.{rail}.{dev}.m0[{param}]' for rail in ('xhigh','xlow') for dev in (('xin','xip','xt','xmp','xmn','xout','xload') if shared_iq else ('xin','xip','xout','xload')) for param in ('vds','vdsat','vgs','id')]
manifest=dict(source_sha256_before=before,baseline_deck_sha256=sha(src),probes=probes,shared_iq=shared_iq,scope='Observation-only, one original210ns stream; original waveform plus device data. 3ns elaboration preflight is not performance evidence.')
(O/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
original=src.read_text();d=original.replace('tran 5p 209.9n 0 5p','save all '+' '.join(probes)+'\ntran 5p 209.9n 0 5p')
d=d.replace('.endc','wrdata /work/devices.dat '+' '.join(probes)+'\n.endc')
rows=[]
for name,horizon in (('preflight',3),('connected',209.9)):
 deck=d if name=='connected' else d.replace('tran 5p 209.9n 0 5p','tran 5p 3n 0 5p').replace('/work/'+wave_name,'/work/preflight.dat').replace('/work/devices.dat','/work/preflight-devices.dat')
 p=O/(name+'.spice');p.write_text(deck);pre=sha(p)
 with (O/(name+'.log')).open('w') as log:
  try:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=3600);code=r.returncode;timeout=False
  except subprocess.TimeoutExpired:code=None;timeout=True
 outputs=[name+'.spice',name+'.log']+(['preflight.dat','preflight-devices.dat'] if name=='preflight' else [wave_name,'devices.dat'])
 rows.append(dict(name=name,horizon_ns=horizon,returncode=code,timed_out=timeout,deck_sha256_before=pre,artifacts_sha256={file:sha(O/file) for file in outputs if (O/file).exists()}))
 (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,code,flush=True)
 if name=='preflight':
  import numpy as np
  assert code==0 and not timeout
  a=np.loadtxt(O/'preflight-devices.dat',skiprows=1);assert a.shape[1]==len(probes)+1 and np.isfinite(a).all() and a[-1,0]>=3e-9
  # Saved device parameters must be actual time vectors, not scalar final OP values.
  assert np.ptp(a[:,1])>0
 after={str(p):sha(p) for p in sources};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n')
