"""Circuit reduction of failing buffered mixed-source case; retain actual PFD."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');src=B/'pwl.spice';base=json.loads((B/'result.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
case=next(c for c in base['cases'] if c['name']=='pwl');assert sha(src)==case['artifacts_sha256']['.spice']
sources=[Path(p) for p in base['source_sha256_before']];before={str(p):sha(p) for p in sources}
original=src.read_text().split('.control')[0];prefixes=('IP ','IN ','XCP ','VSENSE ','XFILT ','.ic ')
removed=[s for s in original.splitlines(keepends=True) if s.startswith(prefixes)];assert len(removed)==6
circuit=''.join(s for s in original.splitlines(keepends=True) if not s.startswith(prefixes))
d=circuit+'''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
save v(REFRAW) v(REF) v(FB) v(UP) v(DN)
tran 2p 800n 0 2p uic
wrdata /work/pfd.dat v(REFRAW) v(REF) v(FB) v(UP) v(DN)
.endc
.end
'''
p=O/'pfd.spice';p.write_text(d);pre=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(src),deck_sha256_before=pre,removed_lines=removed,scope='Actual buffer/PFD and50fF outputs; pump/filter and their gate loading removed; exact clock/reset sources retained'),indent=2)+'\n')
with (O/'pfd.log').open('w') as log:
 try:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=600);code=r.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
after={str(p):sha(p) for p in sources};assert before==after and sha(p)==pre
(O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={ext:sha(O/('pfd'+ext)) for ext in ('.spice','.log','.dat') if (O/('pfd'+ext)).exists()}),indent=2)+'\n');print(code,flush=True)
