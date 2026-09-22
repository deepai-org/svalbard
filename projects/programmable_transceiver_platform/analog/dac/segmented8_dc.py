"""Connected actual decoder/driver/segmented current DAC, all-code static test."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');PDK=Path('/foss/pdks/gf180mcuD/libs.tech/ngspice')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
circuit=[Path('/screen')/s for s in ('dac/current_steering8.spice','dac/thermometer4.spice','dac/segmented8.spice','adc/code_driver_small.spice')]
sources=circuit+list(PDK.glob('*.spice'))+list(PDK.glob('*.ngspice'));before={str(p):sha(p) for p in sources}
d='* Actual segmented converter with ideal input commands, bias current and termination\n.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice\n.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical\n'
d+=''.join(f'.include {p}\n' for p in circuit)
d+='''.temp 27
VDD VDD 0 3.3
VDRV VDRV 0 3.3
IREF VDD BN 20u
XREF BN BN 0 0 nfet_03v3 w=10u l=1u
VTERM TERM 0 2.15
RP TERM OP 100
RN TERM ON 100
VCODE CODE 0 0
'''
for i in range(8):d+=f'BD{i} D{i} 0 V=3.3*(floor(v(CODE)/{2**i})-2*floor(v(CODE)/{2**(i+1)}))\n'
d+='XD OP ON BN VDRV 0 '+' '.join(f'D{i}' for i in range(8))+' pt_dac_segmented8\n'
vectors='v(OP) v(ON) v(BN) i(VDRV) '+' '.join(f'v(D{i})' for i in range(8))+' '+' '.join(f'v(XD.T{k})' for k in range(1,16))
d+='.control\nset wr_singlescale\nset wr_vecnames\nset numdgt=15\ndc VCODE 0 255 1\nwrdata /work/segmented.dat '+vectors+'\n.endc\n.end\n'
p=O/'segmented.spice';p.write_text(d)
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,deck_sha256_before=sha(p)),indent=2)+'\n')
with (O/'segmented.log').open('w') as log:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=300)
after={str(p):sha(p) for p in sources}
(O/'result.json').write_text(json.dumps(dict(returncode=r.returncode,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={s:sha(O/('segmented'+s)) for s in ('.spice','.log','.dat') if (O/('segmented'+s)).exists()}),indent=2)+'\n');assert before==after
