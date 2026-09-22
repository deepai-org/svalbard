"""Isolated track-mode closed-loop response; not a phase-margin or ADC proof."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');PDK=Path('/foss/pdks/gf180mcuD/libs.tech/ngspice');rows=[]
for corner in ('typical','ss','ff'):
 for cc in (.5,1,2):
  name=f'{corner}_cc{cc:g}'
  d=f'''* Actual buffer and sampler, explicit MIM load; isolated track-mode AC
.include {PDK}/design.ngspice
.lib {PDK}/sm141064.ngspice typical
.lib {PDK}/sm141064.ngspice mimcap_{corner}
.include /screen/adc/sample_driver_headroom.spice
.include /wifi/rf_if_transmission_gate/rf_if_transmission_gate.spice
.temp 27
VDD VDD 0 3.3
VP GP 0 DC 1.65 AC .5
VN GN 0 DC 1.65 AC -.5
IBN VDD BN 20u
IBP BP 0 20u
XBN BN BN 0 0 nfet_03v3 w=8u l=.5u
XBP BP BP VDD VDD pfet_03v3 w=8u l=.5u
XP GP IP BN BP VDD 0 pt_sample_driver_headroom CC={cc}p
XN GN IN BN BP VDD 0 pt_sample_driver_headroom CC={cc}p
XS IP IN HP HN VDD 0 VDD 0 wifi_if_transmission_gate
'''
  for leg in ('P','N'):
   for i in range(256):d+=f'XC{leg}{i} H{leg} 0 cap_mim_1f5_m4m5_noshield c_length=5u c_width=5u\n'
  d+=f'''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
ac dec 80 1k 10G
let held=v(HP)-v(HN)
let drive=v(IP)-v(IN)
let hr=real(held)
let hi=imag(held)
let dr=real(drive)
let di=imag(drive)
wrdata /work/{name}.dat hr hi dr di
.endc
.end
'''
  (O/(name+'.spice')).write_text(d)
  with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
  rows.append(dict(name=name,corner=corner,compensation_pf=cc,artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')}))
  print('Completed '+name,flush=True)
sources=[Path('/screen/adc/sample_driver_headroom.spice'),Path('/wifi/rf_if_transmission_gate/rf_if_transmission_gate.spice'),PDK/'sm141064_mim.spice']
(O/'result.json').write_text(json.dumps(dict(status='isolated_track_mode_ac_unverified',cases=rows,source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},limitations=['All capacitor bottoms AC grounded; excludes actual switched CDAC, finite references, comparator and repeated conversion.', 'Small signal at 1.65V common mode, sampler continuously on, FET typical only.', 'Compensation capacitor remains ideal; closed-loop response is not return-ratio/phase-margin qualification.']),indent=2)+'\n')
