"""Trace controller storage and named bit ports through the submitted ADC layout.
Usage: python controller_trace.py SUBMITTED.gds
Connectivity only; no inferred latch timing or asserted SAR bit order.
"""
import contextlib,json,os,runpy,sys
from pathlib import Path
with open(os.devnull,'w') as sink,contextlib.redirect_stdout(sink):
 e=runpy.run_path(str(Path(__file__).with_name('reference_drivers.py')))
l,c,x,regs,k=[e[n] for n in ['l','c','x','regs','k']]
labels={};storage=[]
def ports(cell,tr):
 result={}
 for layer,key in [(34,'m1'),(36,'m2'),(42,'42'),(46,'46'),(81,'81')]:
  for shape in cell.shapes(l.layer(layer,10)).each():
   if not shape.is_text():continue
   name=shape.text.string
   if name in ['vdd','vss']:continue
   net=x.probe_net(regs[key],shape.text.transformed(tr).trans.disp)
   if net:result[name]=net.expanded_name()
 return result
def visit(cell,tr,path):
 if cell.name in ['adc_controller_async_part1_offcal','adc_controller_valid_probe_offcal']:
  for name,net in ports(cell,tr).items():labels.setdefault(net,[]).append(cell.name+':'+name)
 if cell.name in ['lib_dff','lib_dff_wreset']:
  storage.append(dict(instance=path,cell=cell.name,ports=ports(cell,tr)))
 for index,inst in enumerate(cell.each_inst()):
  for ai,t in enumerate(inst.cell_inst.each_trans()):visit(inst.cell,tr*t,path+f'/{inst.cell.name}[{index},{ai}]')
visit(c,k.Trans(),c.name)
for row in storage:row['port_aliases']={pin:labels.get(net,[]) for pin,net in row['ports'].items()}
links=[]
for left in storage:
 for output in ['q','qb']:
  net=left['ports'].get(output)
  if net is None:continue
  for right in storage:
   if right['ports'].get('d')==net:links.append(dict(source=left['instance'],source_port=output,destination=right['instance']))
sequence=[r for r in storage if r['cell']=='lib_dff_wreset']
assert len(sequence)==14 and len(storage)==42
qnodes={r['ports']['q'] for r in sequence}
heads=[r for r in sequence if r['ports']['d'] not in qnodes];assert len(heads)==1
chain=[];current=heads[0]
while True:
 captures=[r for r in storage if r['cell']=='lib_dff' and r['ports']['clk']==current['ports']['q']]
 assert len(captures)==2
 aliases=sorted(a for r in captures for a in r['port_aliases']['q'] if a.startswith('adc_controller_async_part1_offcal:'))
 index=len(chain)+1
 assert aliases==[f'adc_controller_async_part1_offcal:bn<{index}>',f'adc_controller_async_part1_offcal:bp<{index}>']
 chain.append(dict(stage=index,sequence_q=current['ports']['q'],capture_outputs=aliases))
 following=[r for r in sequence if r['ports']['d']==current['ports']['q']]
 if not following:break
 assert len(following)==1 and len(chain)<14
 current=following[0]
assert len(chain)==14
assert len({r['ports']['clk'] for r in sequence})==1
assert len({r['ports']['rstb'] for r in sequence})==1
print(json.dumps(dict(source_sha256=e['hashlib'].sha256(e['path'].read_bytes()).hexdigest(),
 sequence_chain=chain,storage=storage,direct_data_links=links,
 driver_gate_aliases=[dict(array_index=r['array_index'],bit=r['bit_label'],gate=r['gate_node'],aliases=labels.get(r['gate_node'],[])) for r in e['rows']],
 limitations=['Generic parent connectivity; storage cell names do not alone prove active edge, reset truth table or timing.',
 'Direct output-to-data links omit combinational logic; no inferred SAR switching sequence.',
 'Special devices and parasitic delays are not qualified by this trace.']),indent=2))
