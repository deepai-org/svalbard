"""Replace direct ideal CDAC control drives with PDK transistor buffers."""
import hashlib,json,re,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');B=Path('/baseline');rows=[]
for code in (64,127,129,192):
 name=f'code{code}';base=(B/f'code{code}_a1.spice').read_text();d=base
 for bit in range(8):
  original=re.search(rf'^VB{bit} B{bit} 0 (.+)$',d,re.M).group(1)
  d=re.sub(rf'^VB{bit} B{bit} 0 .+$',f'VD{bit} D{bit} 0 '+original,d,flags=re.M)
  d=re.sub(rf'^VB{bit}B B{bit}B 0 .+\n','',d,flags=re.M)
  d=d.replace('.control',f'XDRV{bit} D{bit} B{bit} B{bit}B VDRV 0 pt_adc_code_small_driver WEIGHT={2**bit}\n.control')
 d=d.replace('.control','.include /screen/adc/code_driver_small.spice\nVDRV VDRV 0 3.3\n.control')
 d=d.replace(f'/work/code{code}_a1.dat',f'/work/{name}.dat')
 probes=' '.join(f'v(B{i}) v(B{i}B)' for i in range(8))
 d=d.replace('i(VHR) i(VLR)\n','i(VHR) i(VLR) i(VDRV) '+probes+'\n')
 (O/(name+'.spice')).write_text(d)
 with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
 a=np.loadtxt(O/(name+'.dat'),skiprows=1);assert a.shape[1]==27 and np.isfinite(a).all()
 rows.append(dict(name=name,code=code,baseline_deck_sha256=hashlib.sha256(base.encode()).hexdigest(),artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')}))
sources=json.loads((B/'result.json').read_text())['source_sha256'];sources['/screen/adc/code_driver_small.spice']=hashlib.sha256(Path('/screen/adc/code_driver_small.spice').read_bytes()).hexdigest()
r=dict(status='small_cdac_gate_driver_screen_not_sar',cases=rows,source_sha256=sources,limitations=['Matched TT 3.3V 27C, ideal capacitors and reference fixtures unchanged.', 'Actual three-inverter driver with unequal true/complement paths, no enforced nonoverlap.', 'Logic commands remain ideal and drive first-stage input capacitance; SAR controller and its timing/power absent.', 'Driver supply ideal and separately metered; no PDN coupling, physical parasitics or mismatch.', 'Only four scripted code transitions and return; not ADC transfer/ENOB qualification.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n');print('Completed four transistor code-driver cases.')
