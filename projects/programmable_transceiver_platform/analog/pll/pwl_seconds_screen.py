"""Exact rational timestamp representation change in retained active reproducer."""
import hashlib,json,re,subprocess
from decimal import Decimal
from pathlib import Path
O=Path('/work');B=Path('/baseline');src=B/'pwl.spice';base=json.loads((B/'result.json').read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
case=next(c for c in base['cases'] if c['name']=='pwl');assert sha(src)==case['artifacts_sha256']['.spice']
sources=[Path(p) for p in base['source_sha256_before']];before={str(p):sha(p) for p in sources}
original=src.read_text();old=next(x for x in original.splitlines() if x.startswith('VREF '));tokens=old.split('PWL(',1)[1].removesuffix(')').split();newtokens=tokens.copy()
for i in range(0,len(tokens),2):
 assert tokens[i].endswith('p')
 value=Decimal(tokens[i][:-1])*Decimal('1e-12');newtokens[i]=format(value,'f');assert Decimal(newtokens[i])==value
new=old.split('PWL(',1)[0]+'PWL('+' '.join(newtokens)+')'
d=original.replace(old,new).replace('/work/pwl.dat','/work/seconds.dat');assert d.replace(new,old).replace('/work/seconds.dat','/work/pwl.dat')==original
p=O/'seconds.spice';p.write_text(d);pre=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(src),deck_sha256_before=pre,scope='Exact decimal timestamp values unchanged; PWL p suffix replaced by explicit seconds; same buffer/PFD/pump/filter and PULSE feedback'),indent=2)+'\n')
with (O/'seconds.log').open('w') as log:
 try:r=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=600);code=r.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
after={str(p):sha(p) for p in sources};assert before==after and sha(p)==pre
(O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={ext:sha(O/('seconds'+ext)) for ext in ('.spice','.log','.dat') if (O/('seconds'+ext)).exists()}),indent=2)+'\n');print(code,flush=True)
