"""Audit the installed capacitor primitive before replacing ideal CDAC elements."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');PDK=Path('/foss/pdks/gf180mcuD/libs.tech/ngspice');rows=[]
for corner in ('typical','ss','ff'):
 for par in (1,2):
  for bias in (0,1):
   name=f'{corner}_p{par}_v{bias}'
   d=f'''* Installed MIM primitive behavior at supported PCell minimum geometry
.include {PDK}/design.ngspice
.lib {PDK}/sm141064.ngspice mimcap_{corner}
.temp 27
VTEST TOP 0 DC {bias} AC 1
XC TOP 0 cap_mim_1f5_m4m5_noshield c_length=5u c_width=5u par={par}
.control
set wr_singlescale
set wr_vecnames
set numdgt=15
ac lin 1 1Meg 1Meg
wrdata /work/{name}.dat i(VTEST)
.endc
.end
'''
   (O/(name+'.spice')).write_text(d)
   with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
   a=np.loadtxt(O/(name+'.dat'),skiprows=1);assert len(a)==3 and np.isfinite(a).all()
   rows.append(dict(name=name,corner=corner,par=par,bias_v=bias,capacitance_f=float(-a[2]/(2*np.pi*a[0])),artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')}))
model=PDK/'sm141064_mim.spice';pcell=PDK.parent/'klayout/tech/pymacros/cells/cap_mim.py'
r=dict(status='installed_mim_model_behavior_audit_not_process_qualification',cases=rows,source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (model,pcell,PDK/'sm141064.ngspice')},limitations=['Specific installed 1.5fF/um2 M4-M5 model, 5um by 5um, 27C; stack/process selection still needs project signoff.', '5um dimension is the installed PCell minimum, not independent proof of every foundry fabrication rule.', 'Model test cannot validate real mismatch, leakage, voltage coefficient, RF parasitics or process tails.', 'No layout generated and no change to the current ideal CDAC; its 20fF unit is not validated by this audit.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(rows,indent=2))
