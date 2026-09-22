"""Zero-volt branch sensors; preserve model id probes for comparison."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());before={p:sha(Path(p)) for p in r['source_sha256_before']};assert before==r['source_sha256_before']==r['source_sha256_after']
case=r;assert case['returncode']==0 and not case['timed_out']
source=B/'early.spice';assert sha(source)==case['artifacts_sha256']['.spice']
cell=Path('/screen/pll/charge_pump.spice').read_text()
assert cell.count('XPU OUT ')==cell.count('XND OUT ')==1
modified=cell.replace('XPU OUT ','XPU DP ').replace('XND OUT ','XND DNODE ').replace('.ends pt_charge_pump','VP DP OUT 0\nVN OUT DNODE 0\n.ends pt_charge_pump')
original=source.read_text();assert original.count('.include /screen/pll/charge_pump.spice')==1
original=original.replace('.include /screen/pll/charge_pump.spice',modified.rstrip())
probes=['i(v.xcp.vp)','i(v.xcp.vn)','v(xcp.dp)','v(xcp.dnode)']
d='\n'.join(line+' '+' '.join(probes) if line.startswith(('save ','wrdata ')) else line for line in original.splitlines())+'\n'
p=O/'early.spice';p.write_text(d);h=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(baseline_deck_sha256=sha(source),source_sha256_before=before,probes=probes,cell_sha256=sha(Path('/screen/pll/charge_pump.spice')),scope='Only two zero-volt drain sensors and four saved vectors; ideal clamp remains.'),indent=2)+'\n')
with (O/'early.log').open('w') as log:
 try:s=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=300);code=s.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
after={p:sha(Path(p)) for p in before};assert after==before and sha(p)==h
(O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={e:sha(O/('early'+e)) for e in ('.spice','.log','.dat') if (O/('early'+e)).exists()}),indent=2)+'\n');print(code,timeout,flush=True)
