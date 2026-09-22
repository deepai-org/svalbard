#!/usr/bin/env python3
"""Exercise installed GF180 variation switches and flicker corner, not yield."""
import hashlib,json,re,subprocess
from pathlib import Path
import numpy as np
OUT=Path('/work'); PDK=Path('/foss/pdks/gf180mcuD/libs.tech/ngspice')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cases=[]
settings=[('typical',0,0,s,0) for s in (11,23)]+[('statistical',g,m,s,0) for g,m in ((0,0),(1,0),(0,1),(1,1)) for s in (11,23,47)]+[('statistical',1,1,11,0),('typical',0,0,11,1)]
for index,(lib,g,m,seed,fnoi) in enumerate(settings):
 name=f'{index:02}_{lib}_g{g}m{m}_s{seed}_f{fnoi}'
 noise=OUT/(name+'.dat'); path=OUT/(name+'.spice')
 deck=f'''* Installed-model behavior experiment; two independent identical devices.
.include {PDK}/design.ngspice
.param sw_stat_global={g} sw_stat_mismatch={m} fnoicor={fnoi}
.lib {PDK}/sm141064.ngspice {lib}
.temp 27
V1 VDD1 0 3.3
V2 VDD2 0 3.3
VG G 0 DC 1.0 AC 1
R1 VDD1 D1 1k
R2 VDD2 D2 1k
X1 D1 G 0 0 nfet_03v3 w=4u l=0.28u m=1
X2 D2 G 0 0 nfet_03v3 w=4u l=0.28u m=1
.control
setseed {seed}
reset
op
print i(V1) i(V2) v(D1) v(D2)
set wr_singlescale
set wr_vecnames
noise v(D1) VG dec 20 1k 3g
setplot noise1
wrdata {noise} onoise_spectrum inoise_spectrum
quit
.endc
.end
'''
 path.write_text(deck)
 with (OUT/(name+'.log')).open('w') as log:
  proc=subprocess.run(['ngspice','-b',str(path)],stdout=log,stderr=subprocess.STDOUT,timeout=90)
 text=(OUT/(name+'.log')).read_text()
 vals={k.lower():float(v) for k,v in re.findall(r'^(i\(v[12]\)|v\(d[12]\))\s*=\s*([-+\d.eE]+)',text,re.M|re.I)}
 complete=proc.returncode==0 and len(vals)==4 and noise.exists()
 row=dict(id=name,library=lib,global_switch=g,mismatch_switch=m,seed=seed,flicker_corner=fnoi,complete=complete,observed=vals,deck_sha256=sha(path),log_sha256=sha(OUT/(name+'.log')))
 if complete:
  x=np.loadtxt(noise,skiprows=1)
  assert x.shape[1]==3 and np.isfinite(x).all() and np.all(x[:,1:]>0)
  row['input_noise_v_per_sqrt_hz']={str(f):float(np.interp(np.log10(f),np.log10(x[:,0]),x[:,2])) for f in (1e3,1e6,2.4e9)}
  row['pair_current_difference_a']=abs(vals['i(v1)']-vals['i(v2)'])
 cases.append(row)
 print(json.dumps(row),flush=True)
r=dict(status='model_behavior_screen_not_process_or_rf_validation',cases=cases,
 source_sha256={n:sha(PDK/n) for n in ('design.ngspice','sm141064.ngspice','sm141064.spice')},runner_sha256=sha(Path(__file__)),
 limitations=['Two schematic 4um/0.28um NFETs only; not PEX finger/multiplicity or PMOS/resistor/capacitor statistics.',
 'Three seeds establish switch behavior, not distributions, sigma coverage or fabrication yield.',
 'Linear common-source noise experiment does not establish RF mixer or oscillator phase noise.'])
(OUT/'result.json').write_text(json.dumps(r,indent=2)+'\n')
