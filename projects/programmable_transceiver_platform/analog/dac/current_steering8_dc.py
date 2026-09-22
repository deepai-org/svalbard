"""Static DAC transfer with explicit ideal digital stimulus and output clamps."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');rows=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sources=[Path('/screen/dac/current_steering8.spice'),Path('/foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice'),Path('/foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice')]
pdk=Path('/foss/pdks/gf180mcuD/libs.tech/ngspice')
sources=sorted(set(sources+list(pdk.glob('*.spice'))+list(pdk.glob('*.ngspice'))))
before={str(p):sha(p) for p in sources}
for cm in (1.2,1.65,2.1):
 name=f'cm{cm:g}'
 d=f'''* Actual current DAC, ideal code stimuli and clamped output compliance test
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/dac/current_steering8.spice
.temp 27
VDD VDD 0 3.3
IREF VDD BN 20u
XREF BN BN 0 0 nfet_03v3 w=10u l=1u
VOP OP 0 {cm}
VON ON 0 {cm}
VCODE CODE 0 0
'''
 for i in range(8):
  expression=f'(floor(v(CODE)/{2**i})-2*floor(v(CODE)/{2**(i+1)}))'
  d+=f'B{i} B{i} 0 V=3.3*{expression}\nBB{i} B{i}B 0 V=3.3*(1-{expression})\n'
 d+='XD OP ON BN 0 '+' '.join(f'B{i} B{i}B' for i in range(8))+' pt_current_dac8\n'
 d+=f'''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
dc VCODE 0 255 1
wrdata /work/{name}.dat i(VOP) i(VON) v(BN) {' '.join(f'v(B{i}) v(B{i}B)' for i in range(8))} v(XD.X7.T)
.endc
.end
'''
 (O/(name+'.spice')).write_text(d)
 (O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,planned_cases=['cm1.2','cm1.65','cm2.1'],fixture_scope='DC, FET typical, 3.3V,27C, ideal20uA bias and output clamps, ideal behavioral code stimulus'),indent=2)+'\n')
 with (O/(name+'.log')).open('w') as log:r=subprocess.run(['ngspice','-b',str(O/(name+'.spice'))],stdout=log,stderr=subprocess.STDOUT,timeout=120)
 rows.append(dict(name=name,output_clamp_v=cm,returncode=r.returncode,artifacts_sha256={s:sha(O/(name+s)) for s in ('.spice','.dat','.log') if (O/(name+s)).exists()}));print(name,r.returncode,flush=True)
after={str(p):sha(p) for p in sources};assert before==after
(O/'result.json').write_text(json.dumps(dict(status='first_current_DAC_DC_unverified',cases=rows,source_sha256_before=before,source_sha256_after=after,limitations=['Behavioral sources supply testbench bit controls only; transistor DAC is actual PDK circuitry.', 'Equal clamped outputs, no dynamic voltage swing, finite code driver, reconstruction filter or mixer.', 'Ideal20uA reference, matched FET typical only; no mismatch/noise/glitch/SFDR/settling qualification.']),indent=2)+'\n')
