"""DC input-current disturbance of actual feedback-biased restoring inverter."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');PDK=Path('/foss/pdks/gf180mcuD/libs.tech/ngspice')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sources=[Path('/screen/lo_buffer.spice')]+list(PDK.glob('*.spice'))+list(PDK.glob('*.ngspice'));before={str(p):sha(p) for p in sources}
d='''* Same S1 buffer,200f coupling and100k feedback as connected ring/TX.
.include /foss/pdks/gf180mcuD/libs.tech/ngspice/design.ngspice
.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice typical
.include /screen/lo_buffer.spice
.temp 27
VDD VDD 0 3.3
VSRC SRC 0 1.7
CC SRC IN 200f
RFB IN XBUF.MID 100k
XBUF IN OUT VDD 0 pt_lo_buffer S=1
CLOAD OUT 0 50f
IERR 0 IN 0
.control
set wr_singlescale
set wr_vecnames
set numdgt=15
dc IERR -3u 3u 0.1u
wrdata /work/bias.dat v(IN) v(XBUF.MID) v(OUT) i(VDD)
.endc
.end
'''
p=O/'bias.spice';p.write_text(d);pre=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,deck_sha256_before=pre,scope='Static self-bias with injected+/-3uA; positive current enters IN. No oscillator or RF dynamics.50fF output load diagnostic only.'),indent=2)+'\n')
with (O/'bias.log').open('w') as f:r=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=120)
after={str(p):sha(p) for p in sources};assert before==after and sha(p)==pre
(O/'result.json').write_text(json.dumps(dict(returncode=r.returncode,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={ext:sha(O/('bias'+ext)) for ext in ('.spice','.dat','.log') if (O/('bias'+ext)).exists()}),indent=2)+'\n');print(r.returncode)
