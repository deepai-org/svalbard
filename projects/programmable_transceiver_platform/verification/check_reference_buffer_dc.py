#!/usr/bin/env python3
import argparse,hashlib,json
from pathlib import Path
import numpy as np
parser=argparse.ArgumentParser();parser.add_argument('--complement',action='store_true');args=parser.parse_args()
tag='reference-buffer-complement-dc' if args.complement else 'reference-buffer-dc'
cell='pt_reference_buffer_complement' if args.complement else 'pt_reference_buffer_scaled'
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/('scratch/transceiver-'+tag)
r=json.loads((W/'result.json').read_text());assert len(r['cases'])==12
assert {(c['target_v'],c['scale'],c['direction']) for c in r['cases']}=={(v,s,d) for v in (1.15,2.15) for s in (1,4,16) for d in (-1,1)}
for path,digest in r['source_sha256'].items():assert hashlib.sha256((P/'analog'/path.removeprefix('/screen/')).read_bytes()).hexdigest()==digest
arrays={}
for c in r['cases']:
 name=c['name'];assert c['returncode']==0
 for ext,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+ext)).read_bytes()).hexdigest()==digest
 d=(W/(name+'.spice')).read_text();assert f"VT TARGET 0 {c['target_v']}" in d and f"{cell} S={c['scale']}" in d
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);a=a[np.argsort(a[:,0])];assert a.shape==(81,5) and np.isfinite(a).all() and np.allclose(a[:,0],np.linspace(-.02,.02,81))
 arrays[name]=a;v=c['target_v'];zero=a[40];points=[]
 for load in (-.015,-.003,0,.003,.015):
  k=int(np.argmin(abs(a[:,0]-load)));points.append(dict(load_ma=float(a[k,0]*1e3),output_v=float(a[k,1]),error_mv=float((a[k,1]-v)*1e3),supply_ma=float(-a[k,2]*1e3)))
 c.update(zero_load_error_mv=float((zero[1]-v)*1e3),zero_load_supply_ma=float(-zero[2]*1e3),operating_points=points,output_leaves_supply_rails=bool(np.any((a[:,1]<0)|(a[:,1]>3.3))))
for c in r['cases']:
 other=c['name'].replace('_d1','_d-1') if c['direction']==1 else c['name'].replace('_d-1','_d1')
 c['reverse_sweep_max_output_delta_v']=float(np.max(abs(arrays[c['name']][:,1]-arrays[other][:,1])))
r['status']='reference_driver_static_capacity_audited';r['qualified_reference']=False
r['candidate_disposition']='Unqualified complementary driver; inspect static errors and power before any adoption.' if args.complement else 'Rejected as a direct precision reference driver: static regulation fails at intended high rail even with large scaling.'
r['limitations'].append('Ideal load currents force output outside supply rails in overload cases; these are compliance failures, not safe or valid operating points.')
(P/('evidence/'+tag+'-screen.json')).write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps([{k:c[k] for k in ('name','zero_load_error_mv','zero_load_supply_ma','operating_points')} for c in r['cases'] if c['direction']==1],indent=2))
