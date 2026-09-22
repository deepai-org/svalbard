"""Controlled addition of PMOS switch banks to existing NMOS bridge."""
import hashlib,json,subprocess,time
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((B/'result.json').read_text());sources=[Path(p) for p in base['source_sha256_before']]+[Path('/screen/tx/commutator_tg.spice')]
before={str(p):sha(p) for p in sources};assert all(before[p]==v for p,v in base['source_sha256_before'].items())
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,scope='Only add32 PMOS fingers in parallel to existing32 NMOS; fixed3.3V bulk supply, original biases/loads/codes/LO unchanged.'),indent=2)+'\n')
rows=[]
for c in base['cases']:
 name=c['name'];src=B/(name+'.spice');assert sha(src)==c['artifacts_sha256']['.spice']
 d=src.read_text().replace('XM OP ON RFP RFN LO LOB 0 pt_tx_commutator','XM OP ON RFP RFN LO LOB VDD 0 pt_tx_commutator_tg').replace('.control','.include /screen/tx/commutator_tg.spice\n.control')
 p=O/(name+'.spice');p.write_text(d);pre=sha(p);start=time.monotonic()
 with (O/(name+'.log')).open('w') as f:r=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=180)
 assert sha(p)==pre
 rows.append(dict(name=name,returncode=r.returncode,baseline_deck_sha256=sha(src),elapsed_seconds=time.monotonic()-start,deck_sha256_before=pre,artifacts_sha256={ext:sha(O/(name+ext)) for ext in ('.spice','.log','.dat') if (O/(name+ext)).exists()}));print(name,r.returncode,flush=True)
after={str(p):sha(p) for p in sources};assert before==after
(O/'result.json').write_text(json.dumps(dict(source_sha256_before=before,source_sha256_after=after,cases=rows),indent=2)+'\n')
