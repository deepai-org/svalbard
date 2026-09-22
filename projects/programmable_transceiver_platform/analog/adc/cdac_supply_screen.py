"""Finite driver supply scenarios, with unchanged sampler/CDAC/comparator."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');base=(B/'code127.spice').read_text();rows=[]
for resistance in (.1,1,10):
 for cap in (10,100):
  name=f'r{resistance:g}_c{cap}'
  d=base.replace('VDRV VDRV 0 3.3',f'VDRV DRVSRC 0 3.3\nRDRV DRVSRC VDRV {resistance}\nCDRV VDRV 0 {cap}p').replace('/work/code127.dat',f'/work/{name}.dat').replace('v(B7B)\n','v(B7B) v(VDRV)\n')
  (O/(name+'.spice')).write_text(d)
  with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
  rows.append(dict(name=name,resistance_ohm=resistance,capacitance_pf=cap,artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')}))
r=dict(status='finite_driver_supply_scenarios_not_package_qualification',cases=rows,baseline_deck_sha256=hashlib.sha256(base.encode()).hexdigest(),source_sha256=json.loads((B/'result.json').read_text())['source_sha256'],limitations=['Nominal matched TT 3.3V 27C, major-carry and return only.', 'RC values are scenarios, not measured physical bounds; no inductance, shared ground or RF/PLL coupling.', 'Only driver rail has finite impedance; comparator, sampler, references and command sources retain prior fixtures.', 'No SAR conversion, noise/mismatch or physical capacitor/device parasitics.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n');print('Completed six driver-supply scenarios.')
