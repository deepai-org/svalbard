"""Observation-only replay of low-CM dual ADC, probing both I driver legs."""
import hashlib,json,subprocess
from pathlib import Path
B=Path('/baseline');O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());assert r['returncode']==0 and not r['timed_out'];src=B/'frames.spice';assert sha(src)==r['artifacts_sha256']['.spice'];assert r['source_sha256_before']==r['source_sha256_after']
before={}
for path,h in r['source_sha256_before'].items():
 p=Path('/screen/adc/shared_iq_receiver_cm_before_early.py') if path=='/screen/adc/shared_iq_receiver_cm.py' else Path(path)
 assert sha(p)==h;before[str(p)]=h
before[str(Path(__file__))]=sha(Path(__file__))
probes=' '.join(f'@m.{driver}.{dev}.m0[{param}]' for driver in ('xbpdrv','xbndrv') for dev in ('xt','xip','xin','xout','xload') for param in ('id','vds','vdsat','vgs','vth'))
probes+=' v(GP) v(GN) v(BN) v(BP) v(XBPDRV.T) v(XBPDRV.X) v(XBNDRV.T) v(XBNDRV.X)'
base=src.read_text();assert '\nsave ' not in base
addition='save all '+probes+'\n';d=base.replace('tran 5p',addition+'tran 5p',1)
d='\n'.join(line+' '+probes if line.startswith('wrdata ') else line for line in d.split('\n'));p=O/'frames.spice';p.write_text(d);h=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(baseline_deck_sha256=sha(src),source_sha256_before=before,extra_probes=probes,save_addition=addition,deck_sha256_before=h),indent=2)+'\n')
with (O/'frames.log').open('w') as log:
 try:s=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=900);code=s.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
after={p:sha(Path(p)) for p in before};assert before==after and sha(p)==h
(O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={e:sha(O/('frames'+e)) for e in ('.spice','.log','.dat') if (O/('frames'+e)).exists()}),indent=2)+'\n');print(code,timeout)
