"""Zero-volt output sensors, preserve reference feedback across zero voltage drop."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline');src=B/'connected.spice';base=json.loads((B/'result.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
case=next(c for c in base['cases'] if c['name']=='connected');assert sha(src)==case['artifacts_sha256']['connected.spice']
sources=[Path(p) for p in base['source_sha256_before']];before={str(p):sha(p) for p in sources}
original=src.read_text();old='XREF HR LR VH VL RBN RBP VREFSUP 0 pt_adc_reference_pair_tuned'
new='XREF HR LR VHD VLD RBN RBP VREFSUP 0 pt_adc_reference_pair_tuned\nVHS VHD VH 0\nVLS VLD VL 0'
assert original.count(old)==1;d=original.replace(old,new).replace('.endc','wrdata /work/currents.dat i(VHS) i(VLS) v(VHD) v(VLD) v(VH) v(VL)\n.endc')
assert d.replace(new,old).replace('wrdata /work/currents.dat i(VHS) i(VLS) v(VHD) v(VLD) v(VH) v(VL)\n','')==original
p=O/'current.spice';p.write_text(d);pre=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(src),deck_sha256_before=pre,scope='Ideal0V output sensors only; compare against observation-only baseline before interpreting.'),indent=2)+'\n')
with (O/'current.log').open('w') as log:
 try:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=1800);code=r.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
after={str(p):sha(p) for p in sources}
(O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={n:sha(O/n) for n in ('current.spice','current.log','typical_first-1.dat','devices.dat','currents.dat') if (O/n).exists()}),indent=2)+'\n');assert before==after and sha(p)==pre
