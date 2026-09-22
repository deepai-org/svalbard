import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');base=Path('/chain/chain.spice').read_text();rows=[]
for control in (1.08,1.16,1.24,1.30):
 name=f'v{control:g}'
 d=base.replace('VC CTRL 0 1.08',f'VC CTRL 0 {control}').replace('tran 2p 321n 0 2p uic','tran 2p 41n 0 2p uic').replace('/work/chain.dat',f'/work/{name}.dat')
 p=O/(name+'.spice');p.write_text(d)
 with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
 a=np.loadtxt(O/(name+'.dat'),skiprows=1);assert np.isfinite(a).all() and a[-1,0]>40e-9
 w=a[(a[:,0]>=20e-9)&(a[:,0]<=40e-9)];t=w[:,0];v=w[:,1];i=np.where((v[:-1]<0)&(v[1:]>=0))[0];e=t[i]+(t[i+1]-t[i])*(-v[i])/(v[i+1]-v[i]);assert len(e)>40
 gate=[float(w[:,10].min()),float(w[:,10].max())];assert gate[0]>1.4 and gate[1]<1.6
 rows.append(dict(control_v=control,frequency_hz=float((len(e)-1)/(e[-1]-e[0])),gate_range_v=gate,artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')}));print(json.dumps(rows[-1]),flush=True)
r=dict(status='actual_divider_loaded_wide_vco_tuning_not_pll',cases=rows,slopes_hz_per_v=[(b['frequency_hz']-a['frequency_hz'])/(b['control_v']-a['control_v']) for a,b in zip(rows,rows[1:])],limitations=['Nominal seeded/prebiased RF hierarchy; no acquisition, phase noise or process/mismatch.', 'Four tuning points do not establish global monotonicity or a loop-stability model.', 'Actual mixer/buffer load but ideal biases/sample clocks; actual seven-stage divider/interface/PFD load.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n')
