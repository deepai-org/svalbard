"""Reference-network scenarios around unchanged major-carry CDAC circuit."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');B=Path('/baseline');rows=[]
base=(B/'code127_a1.spice').read_text()
for resistance in (1,10,100):
 for capacitance in (1,10,100):
  name=f'r{resistance}_c{capacitance}'
  d=base.replace('RHR HR VH 10\n',f'RHR HR VH {resistance}\n').replace('RLR LR VL 10\n',f'RLR LR VL {resistance}\n').replace('CHR VH 0 10p\n',f'CHR VH 0 {capacitance}p\n').replace('CLR VL 0 10p\n',f'CLR VL 0 {capacitance}p\n').replace('/work/code127_a1.dat',f'/work/{name}.dat')
  (O/(name+'.spice')).write_text(d)
  with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
  a=np.loadtxt(O/(name+'.dat'),skiprows=1);assert a.shape[1]==10 and np.isfinite(a).all()
  rows.append(dict(name=name,reference_resistance_ohm=resistance,reference_capacitance_pf=capacitance,artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')}))
r=dict(status='cdac_reference_network_scenarios_not_hardware_bounds',cases=rows,baseline_deck_sha256=hashlib.sha256(base.encode()).hexdigest(),source_sha256=json.loads((B/'result.json').read_text())['source_sha256'],limitations=['Only major-carry 128-to-127 and return, matched TT 3.3V 27C.', '1/10/100ohm and 1/10/100pF are scenarios, not measured process/package limits or guaranteed coverage.', 'Ideal reference sources behind passive networks; active driver impedance versus frequency absent.', 'Ideal code/clock sources; no noise/mismatch, autonomous controller, full transfer curve or ADC precision qualification.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n');print('Completed nine reference-network scenarios.')
