"""Conservative single-source passive-network drop bounds, without uniform loads.
For nonnegative sink currents summing to I, each edge carries at most I.
Along any source-to-pin path, |delta V| <= I sum(R); use the shortest R path.
"""
import csv,hashlib,json,sys
from pathlib import Path
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
root=Path(sys.argv[1]);p=root/'projects/programmable_transceiver_platform';out=root/'scratch/transceiver-pdn-ir48'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def distances(edges,source):
 # Parallel edges are alternative paths: never sum their resistance weights.
 pairs={}
 for a,b,r in edges:
  assert np.isfinite(r) and r>0
  key=tuple(sorted((a,b)));pairs[key]=min(r,pairs.get(key,float('inf')))
 nodes=sorted({n for pair in pairs for n in pair});index={n:i for i,n in enumerate(nodes)}
 rows=[];cols=[];values=[]
 for (a,b),r in pairs.items():
  for x,y in [(a,b),(b,a)]:rows.append(index[x]);cols.append(index[y]);values.append(r)
 graph=coo_matrix((values,(rows,cols)),shape=(len(nodes),len(nodes))).tocsr()
 ds=dijkstra(graph,directed=False,indices=index[source])
 assert np.isfinite(ds).all(),'disconnected source network'
 return dict(zip(nodes,map(float,ds)))
t=distances([('s','a',2.),('s','a',20.),('a','b',3.)],'s')
assert t['a']==2 and t['b']==5
for bad in [[('s','a',-1.)],[('s','a',1.),('b','c',1.)]]:
 try:distances(bad,'s')
 except AssertionError:pass
 else:raise AssertionError('invalid graph accepted')
base=json.loads((p/'evidence/pdn-resistance-screen.json').read_text());rails={};audit={}
for net in ['VDD_CORE','VSS_CORE']:
 sourcefile=out/f'{net}.spice';assert sha(sourcefile)==base['artifact_sha256'][sourcefile.name]
 edges=[];loads=[];sources=[]
 for line in sourcefile.read_text().splitlines():
  f=line.split()
  if line.startswith('R'):edges.append((f[1],f[2],float(f[3].split('=')[1])))
  elif line.startswith('I'):loads.append(f[1])
  elif line.startswith('V'):sources.append(f)
 assert len(sources)==1 and sources[0][2]=='0'
 ds=distances(edges,sources[0][1])
 assert sha(out/f'{net}-voltage.csv')==base['artifact_sha256'][f'{net}-voltage.csv']
 rows=list(csv.DictReader((out/f'{net}-voltage.csv').open()));assert len(rows)==len(loads)==26438
 bycell={}
 for row,node in zip(rows,loads):
  expected=f"ITermNode_{row['Layer']}_{round(float(row['X location'])*2000)}_{round(float(row['Y location'])*2000)}"
  assert expected==node
  bycell[row['Instance']]=ds[node]
 rails[net]=bycell;audit[net]={'maximum_path_resistance_ohm':max(bycell.values()),'source':sources[0]}
a,b=rails.values();assert a.keys()==b.keys();combined={n:a[n]+b[n] for n in a}
worst=max(combined,key=combined.get);rmax=combined[worst]
cases=[{'assumed_total_current_ma':ma,'maximum_combined_drop_bound_v':ma/1000*rmax,'minimum_local_supply_bound_v':3.3-ma/1000*rmax,'positive_supply_guarantee':3.3-ma/1000*rmax>0} for ma in [24,48]]
for trial,bound in zip(base['combined'],cases):
 assert trial['assumed_current_ma']==bound['assumed_total_current_ma']
 assert trial['minimum_cell_supply_v']>=bound['minimum_local_supply_bound_v']-1e-8
report={'scope':'Conservative path-resistance bound for arbitrary nonnegative DC cell loads with a specified total; not a bound on actual chip current or process uncertainty',
 'rail_path_bounds':audit,'maximum_combined_path_resistance_ohm':rmax,'worst_bound_instance':worst,'cases':cases,
 'conditional_current_limits_ma':[{'allowed_supply_loss_v':v,'sufficient_total_current_limit_ma':1000*v/rmax} for v in [.05,.1,.2]],
 'proof_outline':['With one ideal source and nonnegative loads, voltage-directed edge flows form an acyclic flow toward sinks; no edge flow can exceed total load current.','Telescoping voltage along any source-to-observation path is bounded by total current times the sum of positive edge resistances.','Shortest resistance paths tighten that valid path bound; VDD and VSS path bounds add at each corresponding cell.','The maximum over cells bounds all observed supplies for every spatial distribution with the assumed total current.'],
 'checks':['Analytic series/parallel-path graph','Negative resistance rejected','Disconnected graph rejected','Retained uniform-load results lie inside the bound'],
 'input_screen_sha256':sha(p/'evidence/pdn-resistance-screen.json'),'source_sha256':sha(p/'verification/pdn_path_bound.py'),
 'limitations':['A bound larger than the supply is vacuous, not a prediction of negative operating voltage or proof a particular load fails.','Assumes positive linear resistors, one ideal feed per rail and only nonnegative cell loads; package dynamics and other voltage sources are excluded.','48mA planning allocation is not a measured or proven upper bound on CORE current.','Nominal extracted model is not a foundry-verified resistance bound; unknown process/feed impedances remain.','Suggested loss values are sensitivity examples, not frozen allowable operating voltages.']}
(p/'evidence/pdn-path-bound.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'rmax':rmax,'cases':cases,'current_limits':report['conditional_current_limits_ma']},indent=2))
