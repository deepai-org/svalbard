"""Matched actual receiver zero/tone histories at approximately 5MHz IF."""
import hashlib,json,subprocess,time
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());before=dict(r['source_sha256_before']);assert before==r['source_sha256_after']
for n,h in before.items():assert sha(Path(n))==h,n
before[str(Path(__file__))]=sha(Path(__file__))
# Derived from prior measured LO2.4954222935GHz; remeasure actual LO in new history.
rf=2.5004222935e9;rows=[]
for name in ('tone','zero'):
 old=next(c for c in r['cases'] if c['name']==name);assert old['returncode']==0 and not old['timed_out']
 src=B/(name+'.spice');assert sha(src)==old['artifacts_sha256']['.spice']
 original=src.read_text();d=original
 line=next(x for x in d.splitlines() if x.startswith('VRF '));assert '2.51542263g' in line
 changed=line.replace('2.51542263g',f'{rf:.4f}')
 assert d.count('tran 2p 401n 0 2p uic')==1
 d=d.replace(line,changed).replace('tran 2p 401n 0 2p uic','tran 2p 1201n 0 2p uic')
 assert d.replace(changed,line).replace('tran 2p 1201n 0 2p uic','tran 2p 401n 0 2p uic')==original
 p=O/(name+'.spice');p.write_text(d);digest=sha(p)
 manifest=dict(parent_deck_sha256=sha(src),deck_sha256=digest,old_source=line,new_source=changed,
  requested_horizon_ns=1201,rf_hz=rf,sources_before=before,
  intended_fit_windows_ns=[[400,800],[800,1200]],scope='Seeded receiver only; no ADC or autonomous feedback; unchanged amplitude, gain and loads.')
 (O/(name+'-manifest.json')).write_text(json.dumps(manifest,indent=2)+'\n')
 start=time.monotonic()
 with (O/(name+'.log')).open('w') as f:
  try:q=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=7200);code=q.returncode;timeout=False
  except subprocess.TimeoutExpired:code=None;timeout=True
 after={n:sha(Path(n)) for n in before};assert after==before and sha(p)==digest
 rows.append(dict(name=name,returncode=code,timed_out=timeout,elapsed_s=time.monotonic()-start,
  artifacts_sha256={ext:sha(O/(name+ext)) for ext in ('.spice','.log','.dat') if (O/(name+ext)).exists()}))
 (O/'progress.json').write_text(json.dumps(dict(cases=rows,sources_before=before,sources_after=after),indent=2)+'\n')
 print(name,code,timeout,flush=True)
(O/'result.json').write_text(json.dumps(dict(cases=rows,sources_before=before,sources_after=after),indent=2)+'\n')
