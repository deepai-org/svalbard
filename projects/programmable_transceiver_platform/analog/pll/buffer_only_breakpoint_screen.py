"""Retain four-FET reference buffer with mixed sources; remove PFD state machine."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');src=B/'pfd.spice';base=json.loads((B/'result.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(src)==base['artifacts_sha256']['.spice'];sources=[Path(p) for p in base['source_sha256_before']];before={str(p):sha(p) for p in sources}
original=src.read_text().split('.control')[0];remove=['XPFD REF FB RN UP DN VDIV 0 pt_pfd\n','CU UP 0 50f\n','CD DN 0 50f\n']
d=original
for line in remove:assert d.count(line)==1;d=d.replace(line,'')
d+='CBUF REF 0 50f\nCFB FB 0 50f\n'
d+='''.control
set wr_singlescale
set wr_vecnames
set numdgt=15
save v(REFRAW) v(REF) v(FB) i(VDIV)
tran 2p 800n 0 2p uic
wrdata /work/buffer.dat v(REFRAW) v(REF) v(FB) i(VDIV)
.endc
.end
'''
p=O/'buffer.spice';p.write_text(d);pre=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(src),deck_sha256_before=pre,removed_lines=remove,scope='Four-FET buffer only,50fF output and feedback loads; ideal clock/reset sources unchanged'),indent=2)+'\n')
with (O/'buffer.log').open('w') as log:
 try:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=300);code=r.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
after={str(p):sha(p) for p in sources};assert before==after and sha(p)==pre
(O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={ext:sha(O/('buffer'+ext)) for ext in ('.spice','.log','.dat') if (O/('buffer'+ext)).exists()}),indent=2)+'\n');print(code,flush=True)
