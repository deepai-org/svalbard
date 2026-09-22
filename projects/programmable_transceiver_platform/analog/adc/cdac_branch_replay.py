"""CDAC terminal-current sensors plus actual control voltages; observation candidate."""
import argparse,hashlib,json,subprocess
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--preflight',action='store_true');args=ap.parse_args()
B=Path('/baseline');O=Path('/work')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((B/'result.json').read_text());assert r['returncode']==0 and not r['timed_out'] and r['source_sha256_before']==r['source_sha256_after']
before={}
for path,h in r['source_sha256_before'].items():
 p=Path('/origin/frames.spice') if path=='/baseline/frames.spice' else Path(path)
 assert sha(p)==h;before[str(p)]=h
before[str(Path(__file__))]=sha(Path(__file__))
assert sha(B/'frames.spice')==r['artifacts_sha256']['.spice'];base=(B/'frames.spice').read_text()
cell=Path('/screen/adc/cdac8_scaled.spice').read_text();old='XN A G Y VSS nfet_03v3 w=2u l=.28u m={S}\nXP A GB Y VDD pfet_03v3 w=4u l=.28u m={S}'
new='VPORT A ASENSE 0\n'+old.replace('XN A ','XN ASENSE ').replace('XP A ','XP ASENSE ');assert cell.count(old)==1
changed=cell.replace(old,new);inc='.include /screen/adc/cdac8_scaled.spice';assert base.count(inc)==1;d=base.replace(inc,changed)
probes=[]
for instance,prefix in [('xd',''),('xq_d','q_')]:
 for bit in range(8):
  probes += [f'v({prefix}b{bit})',f'v({prefix}b{bit}b)']
  for side in ['p','n']:
   path=f'{instance}.x{side}{bit}';probes.append(f'v({path}.bot)')
   for rail in ['h','l']:probes.append(f'i(v.{path}.x{rail}.vport)')
probes=list(dict.fromkeys(probes));wr=next(l for l in base.splitlines() if l.startswith('wrdata '));existing={x.lower() for x in wr.split()[2:]};probes=[x for x in probes if x.lower() not in existing]
newwr=wr+' '+' '.join(probes);d=d.replace(wr,newwr);assert d.replace(newwr,wr).replace(changed,inc)==base
if args.preflight:d=d.replace('tran 5p 209.9n 0 5p','tran 5p 1n 0 5p')
p=O/'frames.spice';p.write_text(d);h=sha(p)
(O/'manifest.json').write_text(json.dumps(dict(baseline_deck_sha256=sha(B/'frames.spice'),source_sha256_before=before,deck_sha256_before=h,extra_probes=probes,requested_horizon_ns=1 if args.preflight else 209.9,scope='0V sensor measures reference-port current into both FETs of each CDAC selector; actual bit gates/bottoms saved. Must validate original waveform reproduction.'),indent=2)+'\n')
with (O/'frames.log').open('w') as log:
 try:run=subprocess.run(['ngspice','-b',str(p)],stdout=log,stderr=subprocess.STDOUT,timeout=900);code=run.returncode;timeout=False
 except subprocess.TimeoutExpired:code=None;timeout=True
after={p:sha(Path(p)) for p in before};assert before==after and sha(p)==h
(O/'result.json').write_text(json.dumps(dict(returncode=code,timed_out=timeout,source_sha256_before=before,source_sha256_after=after,artifacts_sha256={e:sha(O/('frames'+e)) for e in ('.spice','.log','.dat') if (O/('frames'+e)).exists()}),indent=2)+'\n');print(code,timeout)
