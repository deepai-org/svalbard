"""Reuse actual reference followers for dummy tracking; diagnostic DC only."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work'); rows=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
files=list(Path('/screen/reference').glob('buffer_*.spice'))+list(Path('/foss/pdks/gf180mcuD/libs.tech/ngspice').rglob('*.ngspice'))
files += [Path(__file__)]
before={str(p):sha(p) for p in files}
for topology in ('scaled','complement'):
 for scale in (.0625,.25):
  for target in (.9,1.08,1.3):
   name=f'{topology}_s{scale:g}_v{target:g}'
   deck=f'''* Dummy tracking follower DC screen, external bias currents remain
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/reference/buffer_{topology}.spice
.temp 27
VDD VDD 0 3.3
VT TARGET 0 {target}
IBN VDD BN 20u
IBP BP 0 20u
XBN BN BN 0 0 nfet_03v3 w=8u l=.5u
XBP BP BP VDD VDD pfet_03v3 w=8u l=.5u
XBUF TARGET OUT BN BP VDD 0 pt_reference_buffer_{topology} S={scale}
ILOAD OUT 0 0
.control
set wr_singlescale
set wr_vecnames
set numdgt=15
dc ILOAD -150u 150u 5u
wrdata /work/{name}.dat v(OUT) i(VDD) v(XBUF.X) v(XBUF.T) v(BN) v(BP)
.endc
.end
'''
   p=O/(name+'.spice');p.write_text(deck)
   with (O/(name+'.log')).open('w') as log:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=60)
   rows.append(dict(name=name,topology=topology,scale=scale,target_v=target,returncode=r.returncode,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.dat','.log') if (O/(name+e)).exists()}))
   print(name,r.returncode,flush=True)
after={str(p):sha(p) for p in files};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after,limitations=['Ideal20uA bias currents; physical reference generation absent.','DC load sweep is not switched pump response, stability, startup or noise.','TT27C3.3V only; target/load scenarios are not guaranteed physical bounds.']),indent=2)+'\n')
