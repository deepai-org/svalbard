"""Device operating-point diagnostics for the original buffer, not performance qualification."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
O=Path('/work');rows=[]
for cm in (1.2,1.4,1.65,1.9):
 name=f'cm{cm:g}'
 probes=['v(OP)','v(ON)','v(XP.X)','v(XP.T)','v(XN.X)','v(XN.T)','i(VDD)']
 devices=['xp.xip','xp.xin','xp.xt','xn.xip','xn.xin','xn.xt']
 probes += [f'@m.{dev}.m0[{param}]' for dev in devices for param in ('vds','vdsat','vgs','vth','gm','gds')]
 d=f'''* Actual sampling buffer DC headroom diagnosis
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/adc/sample_driver_headroom.spice
.temp 27
VDD VDD 0 3.3
IBN VDD BN 20u
IBP BP 0 20u
XBN BN BN 0 0 nfet_03v3 w=8u l=.5u
XBP BP BP VDD VDD pfet_03v3 w=8u l=.5u
VIP IP 0 {cm+.2}
VIN IN 0 {cm-.2}
XP IP OP BN BP VDD 0 pt_sample_driver_headroom
XN IN ON BN BP VDD 0 pt_sample_driver_headroom
.control
set wr_singlescale
set wr_vecnames
set numdgt=15
op
wrdata /work/{name}.dat {' '.join(probes)}
.endc
.end
'''
 (O/(name+'.spice')).write_text(d)
 with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
 a=np.loadtxt(O/(name+'.dat'),skiprows=1);assert len(a)==44 and np.isfinite(a).all()
 rows.append(dict(name=name,common_mode_v=cm,values={p:float(v) for p,v in zip(probes,a[1:])},artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')}))
r=dict(status='nominal_device_headroom_diagnosis',cases=rows,source_sha256=hashlib.sha256(Path('/screen/adc/sample_driver_headroom.spice').read_bytes()).hexdigest(),limitations=['DC unloaded output; diagnostic of internal device headroom, not sampled-chain timing.', 'PDK model-reported VDSAT compared with VDS is a nominal operating-region diagnostic, not a robustness bound.', 'No noise/mismatch, startup, stability or physical loading qualification.'])
(O/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(rows,indent=2))
