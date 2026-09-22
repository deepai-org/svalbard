"""Actual LNA/ring/quadrature/mixers plus two transistor filter sections."""
import hashlib,json,subprocess,sys,shutil
SETTLING="--settling" in sys.argv
BYPASS="--bypass" in sys.argv
assert not BYPASS or SETTLING
LEVEL10="--level10" in sys.argv
assert not LEVEL10 or BYPASS
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());sources=[Path(p) for p in r['source_sha256_before']];assert {str(p):sha(p) for p in sources}==r['source_sha256_after']
sources += [Path('/screen/bb_filter_section.spice'),Path('/screen/bb_pmos_gain.spice')];before={str(p):sha(p) for p in sources}
addition='''.include /screen/bb_filter_section.spice
VBB BBVDD 0 3.3
VBBIAS BBBIAS 0 2.25
XFI MIP MIN FIP FIN BBBIAS BBVDD 0 pt_bb_filter RFB=20k C=20p
XFQ MQP MQN FQP FQN BBBIAS BBVDD 0 pt_bb_filter RFB=20k C=20p
'''
if BYPASS:
 addition += "".join(f"XCSB{n} LS 0 pt_ref_reservoir_{n}\n" for n in (256,128,64))
 assert Path("/screen/reference/reservoir_mim.spice") in sources
manifest=dict(level10=LEVEL10,bypass=BYPASS,source_sha256_before=before,baseline_deck_sha256={},rf_hz=2.51542263e9,settling=SETTLING,horizon_ns=401 if SETTLING else 201,scope='Two actual filter sections; unchanged mixer terminations; seeded/prebiased RF with UIC; ideal BB supply/bias and passives, no ADC')
rows=[]
for old in r['cases']:
 name=old['name'];src=B/(name+'.spice');assert sha(src)==old['artifacts_sha256']['.spice'];manifest['baseline_deck_sha256'][name]=sha(src)
 d=src.read_text().replace('.control',addition+'.control')
 d='\n'.join(line+' v(FIP) v(FIN) v(FQP) v(FQN) i(VBB) i(VBBIAS)' if line.startswith('wrdata ') else line for line in d.splitlines())+'\n'
 if SETTLING:
  assert d.count('tran 2p 201n 0 2p uic')==1
  d=d.replace('tran 2p 201n 0 2p uic','tran 2p 401n 0 2p uic')
 amp=old['amplitude_v']
 if LEVEL10 and name=='tone':
  assert d.count('VRF RFS 0 SIN(0 0.001 2.51542263g)')==1
  d=d.replace('VRF RFS 0 SIN(0 0.001 2.51542263g)','VRF RFS 0 SIN(0 0.01 2.51542263g)');amp=.01
 p=O/(name+'.spice');p.write_text(d);h=sha(p);(O/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 if LEVEL10 and name=='zero':
  retained=Path('/retained');pr=json.loads((retained/'result.json').read_text())
  assert pr['source_sha256_before']==pr['source_sha256_after']==before
  prior=next(c for c in pr['cases'] if c['name']=='zero')
  assert prior['returncode']==0 and not prior['timed_out']
  for ext,digest in prior['artifacts_sha256'].items():assert sha(retained/(name+ext))==digest
  assert (retained/'zero.spice').read_text()==d
  for ext in ('.dat','.log'):shutil.copyfile(retained/(name+ext),O/(name+ext))
  code=0;timeout=False
 else:
  with (O/(name+'.log')).open('w') as f:
   try:s=subprocess.run(['ngspice','-b',str(p)],stdout=f,stderr=subprocess.STDOUT,timeout=600);code=s.returncode;timeout=False
   except subprocess.TimeoutExpired:code=None;timeout=True
 assert sha(p)==h
 rows.append(dict(name=name,amplitude_v=amp,reused_zero=bool(LEVEL10 and name=='zero'),returncode=code,timed_out=timeout,deck_sha256_before=h,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.log','.dat') if (O/(name+e)).exists()}))
 (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,code,timeout,flush=True)
after={str(p):sha(p) for p in sources};assert before==after
(O/'result.json').write_text(json.dumps(dict(cases=rows,source_sha256_before=before,source_sha256_after=after),indent=2)+'\n')
