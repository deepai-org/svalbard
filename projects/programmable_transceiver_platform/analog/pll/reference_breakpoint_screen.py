"""Test reference breakpoint handling without PLL feedback or active devices."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');rows=[]
for kind,folder in (('pulse','/pulse'),('pwl','/pwl')):
 src=Path(folder)/'closed.spice';line=next(x for x in src.read_text().splitlines() if x.startswith('VREF '))
 d=f'''* Minimal reference-fixture diagnostic, finite passive load
{line}
RLOAD REF OUT 100
CLOAD OUT 0 1p
.options method=gear maxord=2
.control
save v(REF) v(OUT)
tran 2p 3201n 0 2p uic
meas tran final_output FIND v(OUT) AT=3201n
.endc
.end
'''
 (O/(kind+'.spice')).write_text(d)
 with (O/(kind+'.log')).open('w') as log:r=subprocess.run(['ngspice','-b',str(O/(kind+'.spice'))],stdout=log,stderr=subprocess.STDOUT,timeout=180)
 rows.append(dict(kind=kind,returncode=r.returncode,reference_source_deck_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),artifacts_sha256={s:hashlib.sha256((O/(kind+s)).read_bytes()).hexdigest() for s in ('.spice','.log')}));print(kind,r.returncode,flush=True)
(O/'result.json').write_text(json.dumps(dict(status='minimal_reference_diagnostic_unverified',cases=rows),indent=2)+'\n')
