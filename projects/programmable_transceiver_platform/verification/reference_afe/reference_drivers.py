"""Trace reference-switch pairs to actual ADC capacitor bits through the full layout.
Usage: python reference_drivers.py SUBMITTED.gds
Generic connectivity, not a complete simulation-ready ADC or foundry LVS.
"""
import contextlib,hashlib,json,os,runpy,sys
from pathlib import Path
path=Path(sys.argv[1]);sys.argv=['preamp_extract.py',str(path),'adc_top_final_deliver','--json','--bulk','--voltage-classes']
with open(os.devnull,'w') as sink,contextlib.redirect_stdout(sink):
 e=runpy.run_path(str(Path(__file__).with_name('preamp_extract.py')))
l,c,x,regs,k=[e[n] for n in ['l','c','x','regs','k']]
groups={}
for d in e['devices']:
 ty=d['type'];t=d['terminals'];ref='vrefn' if ty=='nmos' else 'vrefp'
 if ty not in ['nmos','pmos'] or ref not in [t['S'],t['D']]:continue
 output=next(v for v in [t['S'],t['D']] if v!=ref)
 groups.setdefault((t['G'],output),{})[ty]=d
assert len(groups)==26 and all(set(g)=={'nmos','pmos'} for g in groups.values())
assert all(g['nmos']['terminals']['B']=='vss' and g['pmos']['terminals']['B']=='vdd' for g in groups.values())
def arrays(cell,transform):
 if cell.name=='lib_cap_array':return [transform]
 result=[]
 for inst in cell.each_inst():
  for tr in inst.cell_inst.each_trans():result.extend(arrays(inst.cell,transform*tr))
 return result
transforms=arrays(c,k.Trans());assert len(transforms)==2
array=l.cell('lib_cap_array');rows=[];seen=set()
for index,transform in enumerate(transforms):
 for shape in array.shapes(l.layer(42,10)).each():
  if not shape.is_text():continue
  label=shape.text.string
  if label=='B12D':continue
  assert label.startswith('B') and label[1:].isdigit()
  point=shape.text.transformed(transform).trans.disp
  node=x.probe_net(regs['42'],point);assert node is not None
  matches=[(key,g) for key,g in groups.items() if key[1]==node.expanded_name()]
  assert len(matches)==1,(label,node.expanded_name())
  key,g=matches[0];assert key not in seen;seen.add(key)
  rows.append(dict(array_index=index,bit_label=label,output_node=key[1],gate_node=key[0],
    nmos_w_um=g['nmos']['parameters']['W'],pmos_w_um=g['pmos']['parameters']['W'],
    nmos_l_um=g['nmos']['parameters']['L'],pmos_l_um=g['pmos']['parameters']['L'],
    nmos_body=g['nmos']['terminals']['B'],pmos_body=g['pmos']['terminals']['B']))
assert len(rows)==26 and len(seen)==26
rows.sort(key=lambda r:(r['array_index'],int(r['bit_label'][1:])))
charge_scenarios=[]
# A single bottom-plate step: floating common node reduces the effective
# switched capacitance; a clamped common node gives the larger endpoint.
for total_pf in [.666,1.5,3.]:
 fraction=4096/8191
 bit_f=total_pf*1e-12*fraction
 for common in ['ideal_floating','clamped']:
  effective_f=bit_f*(1-fraction) if common=='ideal_floating' else bit_f
  charge=effective_f*1.7
  charge_scenarios.append(dict(array_capacitance_pf=total_pf,common_node=common,reference_step_v=1.7,
   assumed_msb_fraction=fraction,charge_pc=charge*1e12,
   mean_current_for_0p5ns_edge_ma=charge/.5e-9*1000,
   minimum_charge_delivery_ns_at_150ua=charge/150e-6*1e9,
   reservoir_only_cap_pf_for_half_lsb_8bit=charge/(1.7/512)*1e12,
   reservoir_only_cap_pf_for_half_lsb_12bit=charge/(1.7/8192)*1e12))
print(json.dumps(dict(source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),cell=c.name,
 reference_high='vrefp',reference_low='vrefn',logic_high='vdd',logic_low='vss',drivers=rows,charge_scenarios=charge_scenarios,
 limitations=['Full-parent generic extraction resolves child supply/reference islands; special MOS capacitors/diodes and parasitics are not fully classified.',
 'Charge screen assumes descending binary weights, a single MSB edge and1.7V reference span; not recovered SAR switching or actual measured capacitance.',
 'Reservoir capacitance assumes it supplies all edge charge without replenishment; ignores ESR/ESL and settling after the edge. Current figure is edge-average, not peak.',
 '150uA comparison is the transceiver model assumption, not the reference-chip current capability.',
 'Connectivity establishes static switch paths and geometry, not SAR decision order, gate waveforms, reference impedance or source/sink capability.']),indent=2))
