"""Static DAC/commutator interface screen; no RF conversion claim."""
import hashlib,json,subprocess,time
from pathlib import Path
O=Path('/work'); B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
old=json.loads((B/'result.json').read_text()); src=B/'segmented.spice'
assert sha(src)==old['artifacts_sha256']['.spice']
new=[Path('/screen/tx/commutator.spice'),Path('/wifi/rf_switch_mixer/mixer.spice')]
sources=[Path(p) for p in old['source_sha256_before']]+new
before={str(p):sha(p) for p in sources}
assert all(before[p]==v for p,v in old['source_sha256_before'].items())
rows=[]
manifest=dict(source_sha256_before=before,baseline_deck_sha256=sha(src),planned_cases=['r50_lo0','r50_lo1','r200_lo0','r200_lo1'],scope='Retain DAC100ohm to2.15V; add passive bridge and per-leg50/200ohm RF loads to ideal1.89V. Static LO only; adverse load scenarios not package bounds.')
(O/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
for load in (50,200):
 for state in (0,1):
  name=f'r{load}_lo{state}'
  add=''.join(f'.include {p}\n' for p in reversed(new))
  add+=f'VLO LO 0 {3.3*state}\nVLOB LOB 0 {3.3*(1-state)}\nVCM CM 0 1.89\nRLP CM RFP {load}\nRLN CM RFN {load}\nXM OP ON RFP RFN LO LOB 0 pt_tx_commutator\n'
  d=src.read_text().replace('.control',add+'.control').replace('/work/segmented.dat',f'/work/{name}.dat')
  d=d.replace('\n.endc',' v(RFP) v(RFN) i(VCM) i(VTERM)\n.endc')
  p=O/(name+'.spice');p.write_text(d);pre=sha(p);start=time.monotonic()
  with (O/(name+'.log')).open('w') as f:
   try:r=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=180);code=r.returncode;timeout=False
   except subprocess.TimeoutExpired:code=None;timeout=True
  assert sha(p)==pre
  rows.append(dict(name=name,load_ohm=load,lo_state=state,returncode=code,timed_out=timeout,elapsed_seconds=time.monotonic()-start,deck_sha256_before=pre,artifacts_sha256={ext:sha(O/(name+ext)) for ext in ('.spice','.dat','.log') if (O/(name+ext)).exists()}))
  (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,code,flush=True)
after={str(p):sha(p) for p in sources};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n')
