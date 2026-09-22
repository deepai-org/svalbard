"""Combine both exact clock sources under passive loads; no active timing circuit."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');rows=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sources=[B/f'{kind}_skew0.spice' for kind in ('pulse','pwl')];before={str(p):sha(p) for p in sources}
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,planned_cases=['pulse','pwl'],scope='Two independent100ohm/1pF passive loads, exact original REF/FB sources, Gear2/UIC; no devices or PLL'),indent=2)+'\n')
for kind in ('pulse','pwl'):
 src=B/f'{kind}_skew0.spice';lines=src.read_text().splitlines();ref=next(x for x in lines if x.startswith('VREF '));fb=next(x for x in lines if x.startswith('VFB '))
 d=f'''* Combined passive clock-source diagnostic
{ref}
{fb}
RR REF RO 100
CR RO 0 1p
RF FB FO 100
CF FO 0 1p
.options method=gear maxord=2
.control
set wr_singlescale
set wr_vecnames
set numdgt=15
save v(REF) v(FB) v(RO) v(FO)
tran 2p 800n 0 2p uic
wrdata /work/{kind}.dat v(REF) v(FB) v(RO) v(FO)
.endc
.end
'''
 p=O/(kind+'.spice');p.write_text(d);pre=sha(p)
 with (O/(kind+'.log')).open('w') as log:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=180)
 rows.append(dict(name=kind,returncode=r.returncode,deck_sha256_before=pre,artifacts_sha256={ext:sha(O/(kind+ext)) for ext in ('.spice','.log','.dat') if (O/(kind+ext)).exists()}));print(kind,r.returncode,flush=True)
after={str(p):sha(p) for p in sources};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n')
