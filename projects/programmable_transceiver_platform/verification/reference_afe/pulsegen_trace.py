"""Map pulse-generator local nets into the full submitted ADC.
Usage: python pulsegen_trace.py SUBMITTED.gds [CELL]
"""
import contextlib,runpy,sys,os,json
from pathlib import Path
path=sys.argv[1];target=sys.argv[2] if len(sys.argv)>2 else 'lib_pulsegen';script=str(Path(__file__).with_name('preamp_extract.py'))
def extract(cell):
 sys.argv=[script,path,cell,'--json','--bulk','--voltage-classes']
 with open(os.devnull,'w') as f,contextlib.redirect_stdout(f):return runpy.run_path(script)
e=extract(target);p=extract('adc_top_final_deliver');k=e['k']
def locate(cell,tr):
 if cell.name==target:return [tr]
 return [out for inst in cell.each_inst() for t in inst.cell_inst.each_trans() for out in locate(inst.cell,tr*t)]
transforms=locate(p['c'],k.Trans());assert len(transforms)==1
tr=transforms[0];mapping={}
for layer in ['poly','m1','m2','42','46','81','nbody']:
 for poly in e['regs'][layer].each():
  pt=poly.point_hull(0);n=e['x'].probe_net(e['regs'][layer],pt)
  if n:
   pn=p['x'].probe_net(p['regs'][layer],tr*pt)
   if pn:mapping.setdefault(n.expanded_name(),set()).add(pn.expanded_name())
print(json.dumps({n:sorted(v) for n,v in mapping.items()},indent=2))
