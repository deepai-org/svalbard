"""All 16 input combinations of an actual transistor decoder; ideal input fixture."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');pdk=Path('/foss/pdks/gf180mcuD/libs.tech/ngspice')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sources=[Path('/screen/dac/thermometer4.spice')]+list(pdk.glob('*.spice'))+list(pdk.glob('*.ngspice'));before={str(p):sha(p) for p in sources}
d='''.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/dac/thermometer4.spice
.temp 27
VDD VDD 0 3.3
VCODE CODE 0 0
'''
for i in range(4):d+=f'BD{i} D{i} 0 V=3.3*(floor(v(CODE)/{2**i})-2*floor(v(CODE)/{2**(i+1)}))\n'
d+='XD D0 D1 D2 D3 '+' '.join(f'T{k}' for k in range(1,16))+' VDD 0 pt_dac_thermometer4\n'
for k in range(1,16):d+=f'CL{k} T{k} 0 20f\n'
d+='.control\nset wr_singlescale\nset wr_vecnames\nset numdgt=15\ndc VCODE 0 15 1\nwrdata /work/decoder.dat '+' '.join(f'v(D{i})' for i in range(4))+' '+' '.join(f'v(T{k})' for k in range(1,16))+' i(VDD)\n.endc\n.end\n'
p=O/'decoder.spice';p.write_text('* Actual CMOS thermometer decoder DC truth table\n'+d)
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,deck_sha256_before=sha(p)),indent=2)+'\n')
with (O/'decoder.log').open('w') as log:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=120)
after={str(p):sha(p) for p in sources}
(O/'result.json').write_text(json.dumps(dict(returncode=r.returncode,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={s:sha(O/('decoder'+s)) for s in ('.spice','.log','.dat') if (O/('decoder'+s)).exists()}),indent=2)+'\n');assert before==after
