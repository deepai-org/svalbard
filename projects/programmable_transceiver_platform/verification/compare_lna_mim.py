#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
b=json.loads((P/'evidence/lna-noise.json').read_text());ideal=json.loads((P/'evidence/lna-bypass.json').read_text())
assert b['completed'] and ideal['completed'];rows=[];hashes={}
for mode in ('clean','lossy','inductive'):
 path=P/('evidence/lna-mim-'+mode+'.json');c=json.loads(path.read_text());assert c['completed'];hashes[mode]=sha(path)
 for p,h in b['provenance']['source_sha256_before'].items():assert c['provenance']['source_sha256_before'][p]==h
 W=R/('scratch/transceiver-lna-mim-'+mode)
 for old,new,record,orig in zip(b['cases'],c['cases'],c['provenance']['cases'],b['provenance']['cases']):
  name=new['name'];assert name==old['name']==record['name']==orig['name']
  for directory,case in ((W,record),(R/'scratch/transceiver-lna-noise',orig)):
   for ext,h in case['artifacts_sha256'].items():assert sha(directory/(name+ext))==h
  d=(W/(name+'.spice')).read_text()
  lines=['.lib /foss/pdks/gf180mcuD/libs.tech/ngspice/sm141064.ngspice mimcap_typical','.include /screen/reference/reservoir_mim.spice']
  node='LS' if mode=='clean' else 'BPC'
  if mode!='clean':lines+=['RCSB LS BPR 5','LCSB BPR BPC '+('3e-10' if mode=='lossy' else '1e-09')]
  lines += [f'XCSB{n} {node} 0 pt_ref_reservoir_{n}' for n in (256,128,64)]
  for line in lines:assert d.count(line+'\n')==1;d=d.replace(line+'\n','')
  assert d==(R/'scratch/transceiver-lna-noise'/(name+'.spice')).read_text()
  newop=np.loadtxt(W/(name+'-op.dat'),skiprows=1);oldop=np.loadtxt(R/'scratch/transceiver-lna-noise'/(name+'-op.dat'),skiprows=1)
  dc_error=float(np.max(abs(newop-oldop)));assert dc_error<1e-12
  rows.append(dict(mode=mode,name=name,dc_vector_max_abs_difference=dc_error,gain=new['source_gain_2p5g'],gain_ratio_to_unbypassed=new['source_gain_2p5g']/old['source_gain_2p5g'],noise_factor_db=new['stationary_noise_factor_db_2p5g'],noise_factor_change_db=new['stationary_noise_factor_db_2p5g']-old['stationary_noise_factor_db_2p5g']))
out=dict(completed=True,evidence_sha256=hashes,explicit_unit_count=448,unit_geometry_um=[5,5],nominal_plate_area_um2=448*25,dc_vector_numerical_comparison_tolerance=1e-12,cases=rows,limitations=['PDK MIM model substitution, not an extracted capacitor bank; total area includes unallocated contacts/spacing/routing.','Series0ohm/0H,5ohm/300pH and5ohm/1nH are selected scenarios, not physical bounds.','Actual switched mixer, bias noise, compression, stability and startup remain unqualified.'])
(P/'evidence/lna-mim-comparison.json').write_text(json.dumps(out,indent=2)+'\n');print('verified',len(rows),'cases')
