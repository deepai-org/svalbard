"""Finite reference source resistance; preserve mixed-source event timing."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');src=B/'buffer.spice';base=json.loads((B/'result.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(src)==base['artifacts_sha256']['.spice'];sources=[Path(p) for p in base['source_sha256_before']];before={str(p):sha(p) for p in sources}
original=src.read_text().split('.control')[0]
original_line=next(line for line in original.splitlines(True) if line.startswith('VREF REFRAW 0 '))
remove=[original_line]
d=original.replace(original_line,original_line.replace('VREF REFRAW 0 ','VREF REFDRIVE 0 ')+'RREF REFDRIVE REFRAW 50\n')
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
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(src),deck_sha256_before=pre,removed_lines=remove,scope='Only reference drive gains50ohm series resistance; mixed clock sources, buffer/reset/load/options unchanged'),indent=2)+'\n')
with (O/'buffer.log').open('w') as log:
 try:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=300);code=r.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
after={str(p):sha(p) for p in sources};assert before==after and sha(p)==pre
(O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={ext:sha(O/('buffer'+ext)) for ext in ('.spice','.log','.dat') if (O/('buffer'+ext)).exists()}),indent=2)+'\n');print(code,flush=True)
