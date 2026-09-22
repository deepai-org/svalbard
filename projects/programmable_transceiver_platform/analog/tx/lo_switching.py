"""Matched ideal-LO transient diagnostic, actual DAC and two bridge variants."""
import hashlib,json,subprocess,time
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((B/'result.json').read_text());src=B/'r50_lo1.spice';c=next(c for c in base['cases'] if c['name']=='r50_lo1');assert sha(src)==c['artifacts_sha256']['.spice']
sources=[Path(p) for p in base['source_sha256_before']];before={str(p):sha(p) for p in sources};assert before==base['source_sha256_before']
vectors='v(OP) v(ON) v(RFP) v(RFN) v(LO) v(LOB) i(VLO) i(VLOB) i(VDD) i(VDRV)'
(O/'manifest.json').write_text(json.dumps(dict(source_sha256_before=before,baseline_deck_sha256=sha(src),vectors=vectors,scope='Fixed codes128/255,50ohm per leg plus1pF each RF output; ideal complementary2.5GHz LO with20ps edges;10ns OP-initialized transient,2ps max step.'),indent=2)+'\n');rows=[]
for variant in ('nmos','tg'):
 for code in (128,255):
  name=f'{variant}_c{code}';d=src.read_text().split('.control')[0]
  if variant=='nmos':d=d.replace('XM OP ON RFP RFN LO LOB VDD 0 pt_tx_commutator_tg','XM OP ON RFP RFN LO LOB 0 pt_tx_commutator')
  d=d.replace('VCODE CODE 0 0',f'VCODE CODE 0 {code}').replace('VLO LO 0 3.3','VLO LO 0 PULSE(0 3.3 1n 20p 20p 180p 400p)').replace('VLOB LOB 0 0.0','VLOB LOB 0 PULSE(3.3 0 1n 20p 20p 180p 400p)')
  assert 'VLOB LOB 0 PULSE' in d
  d+='CRP RFP 0 1p\nCRN RFN 0 1p\n.control\nset wr_singlescale\nset wr_vecnames\nset numdgt=15\nsave '+vectors+'\ntran 2p 10n 0 2p\nwrdata /work/'+name+'.dat '+vectors+'\n.endc\n.end\n'
  p=O/(name+'.spice');p.write_text(d);pre=sha(p);start=time.monotonic()
  with (O/(name+'.log')).open('w') as f:
   try:r=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=240);rc=r.returncode;timeout=False
   except subprocess.TimeoutExpired:rc=None;timeout=True
  assert sha(p)==pre
  rows.append(dict(name=name,variant=variant,code=code,returncode=rc,timed_out=timeout,elapsed_seconds=time.monotonic()-start,deck_sha256_before=pre,artifacts_sha256={ext:sha(O/(name+ext)) for ext in ('.spice','.log','.dat') if (O/(name+ext)).exists()}));print(name,rc,flush=True)
  (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n')
after={str(p):sha(p) for p in sources};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n')
