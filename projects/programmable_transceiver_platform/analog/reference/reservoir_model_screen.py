"""Verify hierarchy expands to intended capacitance with the installed PDK."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');rows=[]
for corner in ('typical','ss','ff'):
 d=f'''* Reference reservoir hierarchy AC check
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_{corner}
.include /screen/reference/reservoir_mim.spice
.temp 27
VTEST TOP 0 DC 2.15 AC 1
XC TOP 0 pt_ref_reservoir_2048
.control
set wr_singlescale
set wr_vecnames
set numdgt=15
ac lin 1 1Meg 1Meg
wrdata /work/{corner}.dat i(VTEST)
.endc
.end
'''
 (O/(corner+'.spice')).write_text(d)
 with (O/(corner+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(O/(corner+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
 a=np.loadtxt(O/(corner+'.dat'),skiprows=1);assert len(a)==3 and np.isfinite(a).all()
 rows.append(dict(corner=corner,capacitance_f=float(-a[2]/(2*np.pi*a[0])),artifacts_sha256={s:hashlib.sha256((O/(corner+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')}))
p=Path('/screen/reference/reservoir_mim.spice')
(O/'result.json').write_text(json.dumps(dict(status='reservoir_AC_unverified',cases=rows,source_sha256=hashlib.sha256(p.read_bytes()).hexdigest()),indent=2)+'\n');print('Completed reservoir AC cases.')
