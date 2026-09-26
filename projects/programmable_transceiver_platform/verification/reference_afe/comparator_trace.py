"""Trace comparator child calibration gates and supply islands through the full ADC.
Usage: python comparator_trace.py SUBMITTED.gds
"""
import contextlib,os,runpy,sys,json,hashlib
from pathlib import Path
path=Path(sys.argv[1]);script=Path(__file__).with_name('preamp_extract.py')
def extract(cell):
 sys.argv=[str(script),str(path),cell,'--json','--bulk','--voltage-classes']
 with open(os.devnull,'w') as sink,contextlib.redirect_stdout(sink):return runpy.run_path(str(script))
e=extract('adc_comp_miyahara_offcal');p=extract('adc_top_final_deliver');k=e['k']
def locate(c,tr,target="adc_comp_miyahara_offcal"):
 if c.name==target:return [tr]
 return [v for i in c.each_inst() for t in i.cell_inst.each_trans() for v in locate(i.cell,tr*t,target)]
trs=locate(p['c'],k.Trans());assert len(trs)==1
mapping={}
for layer in ['poly','m1','m2']:
 found={}
 for poly in e['regs'][layer].each():
  pt=poly.point_hull(0);n=e['x'].probe_net(e['regs'][layer],pt)
  if n and n.expanded_name() in ['$6','$8','vdd','vdd__island2']:
   pn=p['x'].probe_net(p['regs'][layer],trs[0]*pt)
   found[n.expanded_name()]=pn.expanded_name() if pn else None
 mapping[layer]=found
ports={}
for cell_name in ['adc_comp_miyahara_offcal','adc_preamp_v2']:
 transforms=locate(p['c'],k.Trans(),cell_name);assert len(transforms)==1
 child=p['l'].cell(cell_name);ports[cell_name]={}
 for layer,key in [(34,'m1'),(36,'m2'),(42,'42'),(46,'46'),(81,'81')]:
  for shape in child.shapes(p['l'].layer(layer,10)).each():
   if shape.is_text():
    net=p['x'].probe_net(p['regs'][key],shape.text.transformed(transforms[0]).trans.disp)
    if net:ports[cell_name][shape.text.string]=net.expanded_name()
assert ports['adc_preamp_v2']['o_outp']==ports['adc_comp_miyahara_offcal']['i_inp']
assert ports['adc_preamp_v2']['o_outn']==ports['adc_comp_miyahara_offcal']['i_inn']
gate=mapping['poly']['$6'];assert gate==mapping['poly']['$8']
assert mapping['m1']['vdd']==mapping['m1']['vdd__island2']=='vdd'
# Recognize static CMOS NAND by two parallel pull-ups and a two-NMOS stack.
pullups=[d for d in p['devices'] if d['type']=='pmos' and set([d['terminals']['S'],d['terminals']['D']])=={'vdd',gate}]
assert len(pullups)==2
inputs={d['terminals']['G'] for d in pullups};assert 'pad_offcal_en' in inputs
upper=[d for d in p['devices'] if d['type']=='nmos' and gate in [d['terminals']['S'],d['terminals']['D']]]
assert len(upper)==1
ut=upper[0]['terminals'];middle=next(n for n in [ut['S'],ut['D']] if n!=gate)
lower=[d for d in p['devices'] if d['type']=='nmos' and set([d['terminals']['S'],d['terminals']['D']])=={'vss',middle}]
assert len(lower)==1 and {ut['G'],lower[0]['terminals']['G']}==inputs
bias=ports['adc_preamp_v2']['nbias'];assert bias=='pad_vpreamp_bias'
control=dict(preamp_bias_node=bias,calibration_gate_node=gate,logic='NAND',
 inputs=sorted(inputs),disabled_condition='pad_offcal_en=0 forces calibration PMOS gates high in settled static CMOS logic',
 devices=pullups+upper+lower,
 limitations=['Internal second-input timing is not recovered; no calibration sequence or settling time established.',
 'Pad connection establishes external controllability, not the bias or enable used in the published measurement.'])
print(json.dumps(dict(source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),child=e['c'].name,parent=p['c'].name,
 control=control,ports=ports,mapping=mapping,parent_calibration_devices=[d for d in p['devices'] if gate in d['terminals'].values()],
 limitations=['Generic connectivity, not foundry LVS; node identifiers are extraction-local.',
 'Calibration gates share a parent net; its operating voltage/timing is not established by this trace.']),indent=2))
