"""Independent linear DC solve with explicit loads; audit exported source currents."""
import csv,hashlib,json,sys
from pathlib import Path
import numpy as np
import scipy
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import spsolve
root=Path(sys.argv[1]);p=root/'projects/programmable_transceiver_platform';out=Path(sys.argv[2]) if len(sys.argv)>2 else root/'scratch/transceiver-pdn-ir48'
database=Path(sys.argv[3]) if len(sys.argv)>3 else root/'scratch/transceiver-pdn/digital-pdn.odb'
report_path=Path(sys.argv[4]) if len(sys.argv)>4 else p/'evidence/pdn-resistance-screen.json'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
from pdn_linear import solve
# Analytic series-resistor control checks direction, units and source elimination.
t,_,_=solve([('s','a',2.),('a','b',3.)],'s',{'b':.01})
assert abs(t['a']-.02)<1e-12 and abs(t['b']-.05)<1e-12
rail_results={};per_instance={};audits={}
for net in ['VDD_CORE','VSS_CORE']:
 lines=(out/f'{net}.spice').read_text().splitlines();edges=[];currents=[];sources=[]
 for line in lines:
  fields=line.split()
  if line.startswith('R'):edges.append((fields[1],fields[2],float(fields[3].split('=')[1])))
  elif line.startswith('I'):currents.append((fields[1],float(fields[-1])))
  elif line.startswith('V'):sources.append(fields)
 assert len(sources)==1 and sources[0][2]=='0',sources
 source=sources[0][1];assert len(set(n for n,c in currents))==len(currents)==26438
 rows=list(csv.DictReader((out/f'{net}-voltage.csv').open()));assert len(rows)==len(currents)
 # Bind each current node to its exported instance pin by physical coordinate.
 names={}
 for (node,current),row in zip(currents,rows):
  expected=f"ITermNode_{row['Layer']}_{round(float(row['X location'])*2000)}_{round(float(row['Y location'])*2000)}"
  assert node==expected,(node,expected)
  names[row['Instance']]=node
 cases=[]
 for ma in [24,48]:
  loads={n:ma/1000/len(currents) for n,c in currents}
  d,residual,feed=solve(edges,source,loads)
  per_instance[(net,ma)]={name:d[node] for name,node in names.items()}
  cases.append({'assumed_current_ma':ma,'max_cell_rail_drop_v':max(per_instance[(net,ma)].values()),'source_current_a':feed,'max_kcl_residual_a':residual})
 a=per_instance[(net,24)];b=per_instance[(net,48)]
 assert max(abs(b[n]-2*a[n]) for n in a)<1e-8
 rail_results[net]={'resistors':len(edges),'ideal_source':sources[0],'cases':cases}
 audits[net]={'requested_tool_current_a':.048,'exported_current_sum_a':sum(c for n,c in currents)}
combined=[]
for ma in [24,48]:
 a=per_instance[('VDD_CORE',ma)];b=per_instance[('VSS_CORE',ma)];assert a.keys()==b.keys()
 cells={n:3.3-a[n]-b[n] for n in a}
 combined.append({'assumed_current_ma':ma,'minimum_cell_supply_v':min(cells.values()),'maximum_cell_supply_v':max(cells.values()),'worst_instance':min(cells,key=cells.get)})
r={'scope':'Independent nominal exported-resistance DC solve, uniformly distributed explicit fixed currents and one ideal feed per rail; sensitivity only',
 'rails':rail_results,'combined':combined,'rejected_tool_load_assumption':audits,'scipy_version':scipy.__version__,
 'checks':['Analytic series resistor solution','KCL residual and source-current balance','One voltage source per rail','All 26438 current sources mapped to instance pins','24-to-48mA exact linear scaling'],
 'artifact_sha256':{f:sha(out/f) for f in ['VDD_CORE.spice','VSS_CORE.spice','VDD_CORE-voltage.csv','VSS_CORE-voltage.csv','ir.log']},
 'source_sha256':{f:sha(p/'verification'/f) for f in ['solve_pdn_resistance.py','pdn_linear.py','pdn_ir_screen.tcl','run_pdn_ir.sh']},
 'input_database_sha256':sha(database),
 'limitations':['Uniform current and ideal local feed are assumptions, not measured activity or worst-case bounds.','Pinned PDNSim adds automatic and user currents (see pdnsim-load-audit.json); its direct voltage results are not accepted as requested-load results.','No package/feed resistance or inductance, dynamic supply noise, process resistance corners or electromigration qualification.','Resistor topology/models are tool-generated, not independently extracted foundry signoff.','Nominal 3.3V timing cannot be applied directly at the resulting local voltages.']}
report_path.write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(combined,indent=2))
