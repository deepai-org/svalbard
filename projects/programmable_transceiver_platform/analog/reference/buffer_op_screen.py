"""Device headroom of the rejected reference buffer, at compliant DC points."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');B=Path('/baseline');rows=[]
for target in (1.15,2.15):
 for load in (-.015,0,.015):
  name=f'v{target:g}_i{load:g}';src=B/f'v{target:g}_s16_d1.spice';d=src.read_text().split('.control')[0].replace('ILOAD OUT 0 0',f'ILOAD OUT 0 {load}')
  probes=['v(OUT)','v(XBUF.X)','v(XBUF.A)','v(XBUF.T)','i(VDD)']
  devices=['xip','xin','xt','xmp','xmn','xout','xload']
  probes += [f'@m.xbuf.{dev}.m0[{param}]' for dev in devices for param in ('vds','vdsat','vgs','vth','gm','gds','id')]
  d+='.control\nset wr_singlescale\nset wr_vecnames\nset numdgt=15\nop\nwrdata /work/'+name+'.dat '+' '.join(probes)+'\n.endc\n.end\n'
  (O/(name+'.spice')).write_text(d)
  with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
  a=np.loadtxt(O/(name+'.dat'),skiprows=1);assert len(a)==len(probes)+1 and np.isfinite(a).all()
  rows.append(dict(name=name,target_v=target,load_a=load,scale=16,values=dict(zip(probes,map(float,a[1:]))),baseline_deck_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')}))
source=Path('/screen/reference/buffer_scaled.spice')
(O/'result.json').write_text(json.dumps(dict(status='reference_driver_OP_unverified',cases=rows,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest()),indent=2)+'\n');print('Completed six operating points.')
