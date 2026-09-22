"""Actual ADC input-driver DC common-mode screen; not switched-load qualification."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
files=[Path('/screen/adc/sample_driver_headroom.spice'),Path(__file__)]+list(Path('/foss/pdks/gf180mcuD/libs.tech/ngspice').rglob('*.ngspice'))+list(Path('/foss/pdks/gf180mcuD/libs.tech/ngspice').rglob('*.spice'))
before={str(p):sha(p) for p in files};rows=[]
for load in (-100,0,100):
 name=f'load{load}'
 probes=' '.join(f'@m.xbuf.{x}.m0[{q}]' for x in ('xt','xip','xin','xout','xload') for q in ('vds','vdsat'))
 d=f'''* Actual sample driver, same external bias topology as I/Q ADC fixture
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/adc/sample_driver_headroom.spice
.temp 27
VDD VDD 0 3.3
VT TARGET 0 1.07
RS TARGET INPUT 1k
IBN VDD BN 20u
IBP BP 0 20u
XBN BN BN 0 0 nfet_03v3 w=8u l=.5u
XBP BP BP VDD VDD pfet_03v3 w=8u l=.5u
XBUF INPUT OUT BN BP VDD 0 pt_sample_driver_headroom CC=.5p
ILOAD OUT 0 {load}u
.control
set wr_singlescale
set wr_vecnames
set numdgt=15
save v(INPUT) v(OUT) v(XBUF.T) v(XBUF.X) i(VDD) {probes}
dc VT .85 1.85 .01
wrdata /work/{name}.dat v(INPUT) v(OUT) v(XBUF.T) v(XBUF.X) i(VDD) {probes}
.endc
.end
'''
 p=O/(name+'.spice');p.write_text(d)
 with (O/(name+'.log')).open('w') as log:s=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=60)
 rows.append(dict(name=name,load_ua=load,returncode=s.returncode,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.log','.dat') if (O/(name+e)).exists()}))
after={str(p):sha(p) for p in files};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n');print('completed DC runs')
