"""Matched instrumentation and complementary dummy steering; ideal dummy bias."""
import hashlib,json,subprocess
from pathlib import Path
O=Path('/work');B=Path('/baseline')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());before={p:sha(Path(p)) for p in r['source_sha256_before']};assert before==r['source_sha256_before']==r['source_sha256_after']
assert r['returncode']==0 and not r['timed_out'];src=B/'early.spice';assert sha(src)==r['artifacts_sha256']['.spice'];base=src.read_text()
addition='XDNINV DN DNB VDD VSS pt_inv\nXPD DUMMY UP PS VDD pfet_03v3 w=10u l=.28u\nXNDUMMY DUMMY DNB NS VSS nfet_03v3 w=10u l=.28u\n'
rows=[]
for name in ('control','steering'):
 d=base.replace('.control','VDUMMY DUMMY 0 1.08\n.control').replace('/work/early.dat',f'/work/{name}.dat')
 probes=' i(VDIV) i(VDUMMY) v(DUMMY)'
 if name=='steering':
  old='.subckt pt_charge_pump UP DN OUT BP BN VDD VSS';assert d.count(old)==1
  d=d.replace(old,old+' DUMMY').replace('.ends pt_charge_pump',addition+'.ends pt_charge_pump')
  old='XCP UP DN PUMP BPCP BNCP VDIV 0 pt_charge_pump';assert d.count(old)==1
  d=d.replace(old,'XCP UP DN PUMP BPCP BNCP VDIV 0 DUMMY pt_charge_pump');probes+=' v(XCP.DNB)'
 d='\n'.join(line+probes if line.startswith(('save ','wrdata ')) else line for line in d.splitlines())+'\n'
 p=O/(name+'.spice');p.write_text(d);h=sha(p)
 (O/'manifest.json').write_text(json.dumps(dict(baseline_deck_sha256=sha(src),source_sha256_before=before,steering_addition=addition,scope='Control adds power probes and separate unloaded dummy clamp; candidate adds two dummy MOS plus two-FET inverter.'),indent=2)+'\n')
 with (O/(name+'.log')).open('w') as log:
  try:s=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=300);code=s.returncode;timeout=False
  except subprocess.TimeoutExpired:code=None;timeout=True
 assert sha(p)==h
 rows.append(dict(name=name,returncode=code,timed_out=timeout,artifacts_sha256={e:sha(O/(name+e)) for e in ('.spice','.log','.dat') if (O/(name+e)).exists()}))
 (O/'progress.json').write_text(json.dumps(dict(cases=rows),indent=2)+'\n');print(name,code,timeout,flush=True)
after={p:sha(Path(p)) for p in before};assert before==after
(O/'result.json').write_text(json.dumps(dict(source_sha256_before=before,source_sha256_after=after,cases=rows),indent=2)+'\n')
