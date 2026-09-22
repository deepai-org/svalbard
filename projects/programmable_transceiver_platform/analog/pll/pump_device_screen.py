"""Observation-only MOS probes on completed clamped pump fixture."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());before={p:sha(Path(p)) for p in r['source_sha256_before']};assert before==r['source_sha256_before']==r['source_sha256_after']
case=next(c for c in r['cases'] if c['name']=='early');assert case['returncode']==0 and not case['timed_out']
source=B/'early.spice';assert sha(source)==case['artifacts_sha256']['.spice']
probes=[f'@m.xcp.{device}.m0[{quantity}]' for device in ('xps','xpu','xnd','xns') for quantity in ('id','vds','vdsat','vgs','vth')]
d='\n'.join(line+' '+' '.join(probes) if line.startswith(('save ','wrdata ')) else line for line in source.read_text().splitlines())+'\n'
p=O/'early.spice';p.write_text(d);h=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(baseline_deck_sha256=sha(source),source_sha256_before=before,probes=probes,scope='Only saved MOS quantities change; no circuit/stimulus/options change.'),indent=2)+'\n')
with (O/'early.log').open('w') as log:
 try:s=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=300);code=s.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
after={p:sha(Path(p)) for p in before};assert after==before and sha(p)==h
(O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={e:sha(O/('early'+e)) for e in ('.spice','.log','.dat') if (O/('early'+e)).exists()}),indent=2)+'\n');print(code,timeout,flush=True)
