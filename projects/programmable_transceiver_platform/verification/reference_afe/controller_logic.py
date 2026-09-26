"""Recognize static CMOS driver logic from full-parent extracted topology.
Usage: python controller_logic.py FULL_ADC_EXTRACTION.json
Requires the pinned controller/driver trace reports. No timing simulation.
"""
import hashlib,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2];source=Path(sys.argv[1]);j=json.loads(source.read_text())
controller=json.loads((root/'evidence/reference-afe-controller-trace.json').read_text())
drivers=json.loads((root/'evidence/reference-afe-reference-drivers.json').read_text())
assert j['source_sha256']==controller['source_sha256']==drivers['source_sha256']
devices=j['devices']
def connected(node,kind):
 return [d for d in devices if d['type']==kind and node in [d['terminals']['S'],d['terminals']['D']]]
def other(d,node):return next(n for n in [d['terminals']['S'],d['terminals']['D']] if n!=node)
def inverter(node):
 n=connected(node,'nmos');p=connected(node,'pmos')
 if len(n)==len(p)==1 and other(n[0],node)=='vss' and other(p[0],node)=='vdd' and n[0]['terminals']['G']==p[0]['terminals']['G']:
  return n[0]['terminals']['G']
 return None
def nand2(node):
 n=connected(node,'nmos');p=connected(node,'pmos')
 assert len(n)==1 and len(p)==2 and all(other(d,node)=='vdd' for d in p)
 middle=other(n[0],node);stack=connected(middle,'nmos');assert len(stack)==2
 lower=next(d for d in stack if d is not n[0]);assert other(lower,middle)=='vss'
 inputs={d['terminals']['G'] for d in p};assert inputs=={n[0]['terminals']['G'],lower['terminals']['G']}
 return inputs
stored={r['ports']['q']:r for r in controller['storage'] if r['cell']=='lib_dff'}
sequence={r['sequence_q']:r['stage'] for r in controller['sequence_chain']}
rows=[]
for driver in drivers['drivers']:
 nand_output=inverter(driver['gate_node']);assert nand_output
 inputs=nand2(nand_output);decision=[v for v in inputs if v in stored];assert len(decision)==1
 decision=decision[0];valid=next(v for v in inputs if v!=decision)
 trail=[valid]
 while valid not in sequence and inverter(valid) is not None:
  valid=inverter(valid);assert valid not in trail;trail.append(valid)
 aliases=stored[decision]['port_aliases']['q']
 rows.append(dict(array_index=driver['array_index'],bit=driver['bit_label'],decision_aliases=aliases,
   gate_logic='decision AND validity',validity_node=trail[0],validity_buffer_inversions=len(trail)-1,
   validity_origin=valid,sequence_stage=sequence.get(valid),
   rail_selection='gate0 selects VREFP through PMOS; gate1 selects VREFN through NMOS'))
# Common sequence clock is an OR of the two comparator outputs.
seq=[r for r in controller['storage'] if r['cell']=='lib_dff_wreset']
clock=seq[0]['ports']['clk'];nor=inverter(clock);assert nor
ns=connected(nor,'nmos');ps=connected(nor,'pmos')
assert len(ns)==2 and len(ps)==1 and all(other(d,nor)=='vss' for d in ns)
mid=other(ps[0],nor);stack=connected(mid,'pmos');assert len(stack)==2
upper=next(d for d in stack if d is not ps[0]);assert other(upper,mid)=='vdd'
clock_inputs={d['terminals']['G'] for d in ns}
assert clock_inputs=={ps[0]['terminals']['G'],upper['terminals']['G']}
assert clock_inputs=={r['ports']['d'] for r in stored.values()}
reset=seq[0]['ports']['rstb'];reset_origin=inverter(inverter(reset));assert reset_origin
reset_inputs=nand2(reset_origin);assert 'pad_clk' in reset_inputs
node=next(v for v in reset_inputs if v!='pad_clk');delay=[]
while node!='pad_clk':
 ns=connected(node,'nmos');ps=connected(node,'pmos')
 assert len(ns)==len(ps)==1 and other(ps[0],node)=='vdd'
 assert ns[0]['terminals']['G']==ps[0]['terminals']['G']
 tail=other(ns[0],node);tails=[d for d in connected(tail,'nmos') if d is not ns[0]]
 assert len(tails)==1 and other(tails[0],tail)=='vss'
 assert tails[0]['terminals']['G']=='pad_vpulsegen_bias'
 delay.append(node);node=ns[0]['terminals']['G'];assert len(delay)<=20
assert len(delay)==9
handshake=dict(sequence_clock=clock,clock_logic='OR(comp_outp,comp_outn)',
 reset_logic='NAND(pad_clk, delayed_inverted_pad_clk), followed by two inverters',
 delay_stages=len(delay),delay_control='pad_vpulsegen_bias',
 interpretation='With functioning delay stages, a rising pad clock can generate an active-low reset pulse; pulse width depends on externally biased delay and loading.',
 limits='Static topology does not establish pulse width, comparator rearming, reset margins or complete loop stability.')
comp_trace=json.loads((root/'evidence/reference-afe-comparator-trace.json').read_text())
assert comp_trace['source_sha256']==j['source_sha256']
evaluate=comp_trace['ports']['adc_comp_miyahara_offcal']['i_p_amplify']
node=evaluate;buffers=[]
while inverter(node) is not None:
 buffers.append(node);node=inverter(node);assert len(buffers)<30
assert len(buffers)==10
ns=connected(node,'nmos');assert len(ns)==3 and all(other(d,node)=='vss' for d in ns)
inputs={d['terminals']['G'] for d in ns}
# Verify the matching three-device PMOS series stack to VDD.
stack=[];at=node;previous=None
while at!='vdd':
 options=[d for d in connected(at,'pmos') if d is not previous]
 assert len(options)==1
 previous=options[0];stack.append(previous);at=other(previous,at);assert len(stack)<=3
assert len(stack)==3 and inputs=={d['terminals']['G'] for d in stack}
done=controller['sequence_chain'][-1]['sequence_q']
reset_asserted=[v for v in inputs if inverter(v)==reset];assert len(reset_asserted)==1
assert inputs=={clock,done,reset_asserted[0]}
handshake['comparator_evaluate_logic']='NOR(reset_asserted, comparator_valid, stage14_done), through10 inverters'
handshake['evaluate_buffer_inversions']=len(buffers)
handshake['rearming_interpretation']='A valid decision inhibits evaluate; comparator output deassertion can re-enable evaluate after buffer delay unless reset or stage14_done remains asserted.'
handshake['limits']='Static topology establishes feedback and stop logic, not loop pulse widths, successful14-decision completion, reset margins, metastability or hazards.'
print(json.dumps(dict(source_gds_sha256=j['source_sha256'],full_extraction_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),drivers=rows,handshake=handshake,
 limitations=['Static inverter/NAND topology recognition, not foundry LVS or dynamic timing validation.',
 'Any validity origin not matched to a sequence node remains unresolved; no assumed reset or active edge.',
 'Capacitor charge depends on actual rail voltages, initial states and propagation delays.']),indent=2))
