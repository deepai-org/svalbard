"""Fixed-total-current quadrant sensitivity, with matched VDD/VSS cell loads."""
import csv,hashlib,json,sys
from pathlib import Path
from pdn_linear import solve
root=Path(sys.argv[1]);p=root/'projects/programmable_transceiver_platform';out=root/'scratch/transceiver-wide-pdn-ir48'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
base=json.loads((p/'evidence/wide-pdn-resistance.json').read_text())
t,_,_=solve([('s','a',2.),('a','b',3.)],'s',{'b':.01});assert abs(t['b']-.05)<1e-12
models={};positions={}
for net in ['VDD_CORE','VSS_CORE']:
 for file in [f'{net}.spice',f'{net}-voltage.csv']:assert sha(out/file)==base['artifact_sha256'][file]
 edges=[];nodes=[];sources=[]
 for line in (out/f'{net}.spice').read_text().splitlines():
  f=line.split()
  if line.startswith('R'):edges.append((f[1],f[2],float(f[3].split('=')[1])))
  elif line.startswith('I'):nodes.append(f[1])
  elif line.startswith('V'):sources.append(f)
 assert len(sources)==1
 rows=list(csv.DictReader((out/f'{net}-voltage.csv').open()));assert len(nodes)==len(rows)==26438
 names={}
 for row,node in zip(rows,nodes):
  x=float(row['X location']);y=float(row['Y location'])
  assert node==f"ITermNode_{row['Layer']}_{round(x*2000)}_{round(y*2000)}"
  names[row['Instance']]=node
  if net=='VDD_CORE':positions[row['Instance']]=(x,y)
 models[net]=(edges,sources[0][1],names)
assert models['VDD_CORE'][2].keys()==models['VSS_CORE'][2].keys()
groups={'uniform':set(positions)}
for east in [False,True]:
 for north in [False,True]:
  label=('north' if north else 'south')+('_east' if east else '_west')
  groups[label]={n for n,(x,y) in positions.items() if (x>=760)==east and (y>=775)==north}
assert set.union(*(v for k,v in groups.items() if k!='uniform'))==set(positions)
assert sum(len(v) for k,v in groups.items() if k!='uniform')==26438
cases=[]
for label,active in groups.items():
 assert active;rails={};checks={}
 for net,(edges,source,names) in models.items():
  loads={names[n]:.048/len(active) for n in active}
  d,residual,feed=solve(edges,source,loads)
  rails[net]={n:d[node] for n,node in names.items()}
  checks[net]={'source_current_a':feed,'max_kcl_residual_a':residual}
 local={n:3.3-rails['VDD_CORE'][n]-rails['VSS_CORE'][n] for n in positions}
 result={'distribution':label,'active_cells':len(active),'current_per_active_cell_a':.048/len(active),
  'minimum_cell_supply_v':min(local.values()),'maximum_cell_supply_v':max(local.values()),'worst_instance':min(local,key=local.get),'checks':checks}
 cases.append(result);print(label,result['minimum_cell_supply_v'],flush=True)
previous=next(c for c in base['combined'] if c['assumed_current_ma']==48)
assert abs(cases[0]['minimum_cell_supply_v']-previous['minimum_cell_supply_v'])<1e-7
assert abs(cases[0]['maximum_cell_supply_v']-previous['maximum_cell_supply_v'])<1e-7
r={'scope':'Five specified spatial load cases at fixed 48mA total on the wider nominal DC grid; not exhaustive or calibrated activity bounds',
 'region_rule':'Quadrants by VDD instance-pin coordinate relative to x=760um, y=775um. Matching cell currents used on both rails.',
 'cases':cases,'reference_sha256':sha(p/'evidence/wide-pdn-resistance.json'),
 'source_sha256':{f:sha(p/'verification'/f) for f in ['pdn_regional_loads.py','pdn_linear.py']},
 'limitations':['All current uniformly concentrated within each active region; other cells have zero assumed load. Not measured switching/leakage.','Finite quadrant cases do not bound arbitrary within-region hot spots or realistic per-cell current.','One ideal feed per rail, nominal resistor models, no package impedance, dynamics, process corners or EM qualification.','No accepted local-supply tolerance or timing-library envelope established.']}
(p/'evidence/pdn-regional-loads.json').write_text(json.dumps(r,indent=2)+'\n')
