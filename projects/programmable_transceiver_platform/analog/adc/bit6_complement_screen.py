"""Only bit6 complementary driver strength doubles, both channels."""
import hashlib,json,subprocess,time
from pathlib import Path
B=Path('/candidate_base');O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());assert r['returncode']==0 and not r['timed_out'] and r['source_sha256_before']==r['source_sha256_after']
before={}
for name,h in r['source_sha256_before'].items():
 p=Path(name);assert sha(p)==h,name;before[name]=h
before[str(Path(__file__))]=sha(Path(__file__))
assert sha(B/'frames.spice')==r['artifacts_sha256']['.spice']
base=(B/'frames.spice').read_text()
cell=Path('/screen/adc/code_driver_small.spice').read_text().split('.subckt pt_adc_code_small_driver',1)[1]
cell='.subckt pt_adc_code_bit6_fast'+cell
assert cell.count('X2 B BB VDD VSS pt_adc_drive_small_inv S={4*WEIGHT}')==1
cell=cell.replace('X2 B BB VDD VSS pt_adc_drive_small_inv S={4*WEIGHT}','X2 B BB VDD VSS pt_adc_drive_small_inv S={8*WEIGHT}')
anchor='.include /screen/adc/code_driver_small.spice';assert base.count(anchor)==1
deck=base.replace(anchor,anchor+'\n'+cell);changes=[]
for prefix in ('','Q_'):
 old=next(l for l in base.splitlines() if l.startswith('X'+prefix+'DRV6 '));new=old.replace('pt_adc_code_small_driver','pt_adc_code_bit6_fast');assert new!=old
 deck=deck.replace(old,new);changes.append((old,new))
back=deck
for old,new in changes:back=back.replace(new,old)
assert back.replace(anchor+'\n'+cell,anchor)==base
oldout='/work/probed/frames.dat';assert deck.count(oldout)==1;deck=deck.replace(oldout,'/work/frames.dat')
p=O/'frames.spice';p.write_text(deck)
m=dict(parent_deck_sha256=sha(B/'frames.spice'),deck_sha256_before=sha(p),source_sha256_before=before,changes=changes,added_subcircuit=cell,scope='Bit6 complement inverter multiplicity4*WEIGHT to8*WEIGHT only, I/Q; all history and reltol settings retained.',evaluation='Compare both gate transition directions, charge/peaks, all reference decision errors, held voltages, codes and driver supply energy. No automatic promotion from a reduced peak.')
(O/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');start=time.monotonic()
with (O/'frames.log').open('w') as log:
 try:q=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=1800);code=q.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
after={n:sha(Path(n)) for n in before};assert before==after and sha(p)==m['deck_sha256_before']
(O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,elapsed_s=time.monotonic()-start,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={e:sha(O/('frames'+e)) for e in ('.spice','.log','.dat') if (O/('frames'+e)).exists()}),indent=2)+'\n');print(code,timeout)
