"""Closed-loop output impedance at selected DC loads; not a return-ratio test."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');rows=[]
for rail,target,cell,loads in (('high',2.15,'pt_reference_buffer_complement',(-.003,0,.015)),('low',1.15,'pt_reference_buffer_scaled',(-.015,0,.003))):
 for reservoir in ('ideal10p','mim2048'):
  for load in loads:
   name=f'{rail}_{reservoir}_i{load:g}'
   cap='CRES OUT 0 10p' if reservoir=='ideal10p' else 'XRES OUT 0 pt_ref_reservoir_2048'
   d=f'''* Actual reference driver output impedance under DC load
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical
.include /screen/reference/buffer_scaled.spice
.include /screen/reference/buffer_complement.spice
.include /screen/reference/reservoir_mim.spice
.temp 27
VDD VDD 0 3.3
VT TARGET 0 {target}
IBN VDD BN 20u
IBP BP 0 20u
XBN BN BN 0 0 nfet_03v3 w=8u l=.5u
XBP BP BP VDD VDD pfet_03v3 w=8u l=.5u
XBUF TARGET OUT BN BP VDD 0 {cell} S=4
ILOAD OUT 0 DC {load} AC 1
{cap}
.control
set wr_singlescale
set wr_vecnames
set numdgt=15
ac dec 80 1k 10G
let zr=-real(v(OUT))
let zi=-imag(v(OUT))
wrdata /work/{name}.dat zr zi
.endc
.end
'''
   (O/(name+'.spice')).write_text(d)
   with (O/(name+'.log')).open('w') as log:subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
   rows.append(dict(name=name,rail=rail,target_v=target,dc_load_a=load,reservoir=reservoir,artifacts_sha256={s:hashlib.sha256((O/(name+s)).read_bytes()).hexdigest() for s in ('.spice','.dat','.log')}))
source=[Path('/screen/reference')/n for n in ('buffer_scaled.spice','buffer_complement.spice','reservoir_mim.spice')]
(O/'result.json').write_text(json.dumps(dict(status='reference_output_impedance_unverified',cases=rows,source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in source}),indent=2)+'\n');print('Completed twelve output-impedance cases.')
