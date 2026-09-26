"""Closed comparator/controller with optional ideal-sampled capacitor feedback.
Usage: python controller_sim.py RAW_CONTROLLER.json PARENT_MAP.json MODELDIR [STEP_NS] [TIMEOUT_S] [ramp] [STOP_NS] [cdac] [finite] [REF_R_OHM]
"""
import hashlib,json,subprocess,sys,tempfile
from collections import Counter
from pathlib import Path
import numpy as np
raw,mapfile,models=map(Path,sys.argv[1:4]);models=models.resolve()
step=float(sys.argv[4]) if len(sys.argv)>4 else .1
assert 0<step<=.1
ramp=len(sys.argv)>6 and sys.argv[6]=="ramp"
stop=float(sys.argv[7]) if len(sys.argv)>7 else 100.
assert stop in [50.,100.]
cdac=len(sys.argv)>8 and sys.argv[8]=="cdac"
finite=len(sys.argv)>9 and sys.argv[9]=="finite"
if finite:assert cdac and ramp
reference_r=float(sys.argv[10]) if len(sys.argv)>10 else 10.
assert np.isfinite(reference_r) and reference_r>0
j=json.loads(raw.read_text());mapping=json.loads(mapfile.read_text());assert all(len(v)==1 for v in mapping.values())
root=Path(__file__).resolve().parents[2]
trace=json.loads((root/'evidence/reference-afe-controller-trace.json').read_text())
geometry=json.loads((root/'evidence/reference-afe-cap-geometry.json').read_text())
def global_node(n):return n.replace('$','net_')
def node(n):return global_node(mapping[n][0])
with tempfile.TemporaryDirectory(prefix='afe-loop-') as td:
 lines=['Recovered comparator controller loop','.include design.ngspice','.lib sm141064.ngspice typical','.temp 25',
  'VDD vdd 0 3.3','VSS vss 0 0','VRP vrefp 0 2.5','VRN vrefn 0 .8','VOFF pad_offcal_en 0 0',
  f'VP {node("x_dacp")} 0 1.655',f'VN {node("x_dacn")} 0 1.645','VBIAS pad_vpreamp_bias 0 1.2',
  f'VC {node("clk")} 0 PWL(0 3.3 5n 3.3 5.1n 0 50n 0 50.1n 3.3 55n 3.3 55.1n 0 100n 0)',
  '.options reltol=1e-5 abstol=1e-12 vntol=1e-8']
 if ramp:
  for i,line in enumerate(lines):
   fields=line.split()
   if fields and fields[0] in ['VDD','VRP','VRN','VP','VN','VBIAS']:
    lines[i]=' '.join(fields[:3])+f' PWL(0 0 1n {fields[3]})'
  lines=[line.replace('PWL(0 3.3 5n','PWL(0 0 1n 3.3 5n') for line in lines]
 for i,d in enumerate(j['devices']):
  t=d['terminals'];p=d['parameters'];ty=d['type']
  if ty=='resistor':lines.append(f"R{i} {node(t['A'])} {node(t['B'])} {p['R']}");continue
  assert ty in ['nmos','pmos']
  lines.append(f"M{i} {' '.join(node(t[n]) for n in ['D','G','S','B'])} {ty}_3p3 W={p['W']}u L={p['L']}u AD={p['AD']*1e-12} AS={p['AS']*1e-12} PD={p['PD']}u PS={p['PS']}u")
 if cdac:
  lines=[line.replace('VP '+node('x_dacp')+' ','VP source_p ').replace('VN '+node('x_dacn')+' ','VN source_n ') for line in lines]
  lines += ['.model sampler SW(Ron=1 Roff=1e12 Vt=1.65 Vh=0)',
    f'SP {node("x_dacp")} source_p {node("clk")} 0 sampler',
    f'SN {node("x_dacn")} source_n {node("clk")} 0 sampler']
 if finite:
  # Ideal-assisted precharge until4ns, before sampling ends; thereafter both
  # rails use the stated finite-source law. This is not a startup qualification.
  lines=[line.replace('VRP vrefp ','VRP target_p ').replace('VRN vrefn ','VRN target_n ') for line in lines]
  lines += ['CRP vrefp 0 100p','CRN vrefn 0 100p',
   f'BRP 0 vrefp I=ternary_fcn(time<4n,(v(target_p)-v(vrefp))/.1,min(max((v(target_p)-v(vrefp))/{reference_r},-150u),150u))',
   f'BRN 0 vrefn I=ternary_fcn(time<4n,(v(target_n)-v(vrefn))/.1,min(max((v(target_n)-v(vrefn))/{reference_r},-150u),150u))']
 # Exact parallel-device grouping retains each finger's W/L and diffusion
 # geometry. Multiplicity scales identical devices; no width regrouping/bin change.
 mos=Counter(' '.join(line.split()[1:]) for line in lines if line.startswith('M'))
 lines=[line for line in lines if not line.startswith('M')]
 lines += [f'MGROUP{i} {body} m={count}' for i,(body,count) in enumerate(mos.items())]
 assert sum(mos.values())==4501
 for i in range(13):
  cap=geometry['bit_geometry'][f'B{i}']['m3_m4_overlap_um2']*.0394e-15
  for side in ['cap_ctrl','cap_ctrlb']:
   top=node('x_dacp' if side=='cap_ctrl' else 'x_dacn') if cdac else '0'
   lines.append(f'CL{side}{i} {node(side+"<"+str(i)+">")} {top} {cap}')
 stages=[global_node(r['sequence_q']) for r in trace['sequence_chain']]
 clock=global_node(next(r for r in trace['storage'] if r['cell']=='lib_dff_wreset')['ports']['clk'])
 vectors=[clock,node('x_pt_comp'),node('comp_outp'),node('comp_outn')]+stages
 if cdac:vectors += [node('x_dacp'),node('x_dacn')]+[node(f'bp<{i}>') for i in range(1,15)]
 if finite:vectors += ['vrefp','vrefn']
 deck=Path(td)/'loop.cir';wave=Path(td)/'wave.txt'
 lines+=['.save '+ ' '.join(f'v({n})' for n in vectors),'.control','set wr_singlescale','set wr_vecnames','set numdgt=15',f'tran {step}n {stop}n 0 {step}n'+(' uic' if ramp else ''),f'wrdata {wave} '+ ' '.join(f'v({n})' for n in vectors),'.endc','.end']
 deck.write_text('\n'.join(lines)+'\n')
 try:
  proc=subprocess.run(['ngspice','-b',str(deck)],cwd=models,capture_output=True,text=True,timeout=float(sys.argv[5]) if len(sys.argv)>5 else 60)
 except subprocess.TimeoutExpired as exc:
  def decoded(v):return v.decode(errors='replace') if isinstance(v,bytes) else (v or '')
  print(json.dumps(dict(status='timed_out_no_functional_result',supply_ramp_1ns=ramp,maximum_timestep_ns=step,
    source_gds_sha256=j['source_sha256'],raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
    simulator_stdout_tail=decoded(exc.stdout)[-6000:],simulator_stderr_tail=decoded(exc.stderr)[-6000:]),indent=2))
  sys.exit(2)
 assert proc.returncode==0 and wave.exists(),proc.stdout+proc.stderr
 a=np.loadtxt(wave,skiprows=1);rows=[]
 for start,end in [(5,50),(55,100)]:
  if end>stop:continue
  window=(a[:,0]>=start*1e-9)&(a[:,0]<end*1e-9);b=a[window];rises={}
  for i,n in enumerate(vectors):
   ix=np.flatnonzero((b[:-1,i+1]<1.65)&(b[1:,i+1]>=1.65))
   rises[n]=[float(v*1e9) for v in b[ix+1,0]]
  rows.append(dict(window_ns=[start,end],valid_rises_ns=rises[clock],stage_rises_ns=[rises[n] for n in stages],
    final_stage_voltages=[float(b[-1,i+5]) for i in range(14)]))
  if cdac:
   rows[-1]['final_differential_input_v']=float(b[-1,19]-b[-1,20])
   rows[-1]['stored_positive_decisions']=[int(b[-1,i+21]>1.65) for i in range(14)]
   rows[-1]['differential_input_before_valid_edges_v']=[float(np.interp(t*1e-9,b[:,0],b[:,19]-b[:,20])) for t in rises[clock]]
  if finite:
   rows[-1]['high_reference_peak_droop_mv']=float((2.5-min(b[:,-2]))*1000)
   rows[-1]['low_reference_peak_rise_mv']=float((max(b[:,-1])-.8)*1000)
   rows[-1]['reference_voltages_at_valid_edges']=[[float(np.interp(t*1e-9,b[:,0],b[:,i])) for i in [-2,-1]] for t in rises[clock]]
 print(json.dumps(dict(reference_resistance_ohm=reference_r if finite else None,finite_references=finite,capacitor_feedback=cdac,stop_time_ns=stop,exact_mos_groups=len(mos),supply_ramp_1ns=ramp,maximum_timestep_ns=step,source_gds_sha256=j['source_sha256'],raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),map_sha256=hashlib.sha256(mapfile.read_bytes()).hexdigest(),model_sha256={n:hashlib.sha256((models/n).read_bytes()).hexdigest() for n in ["design.ngspice","sm141064.ngspice"]},cycles=rows,
  limitations=[('Nominal3.3V25C,10mV differential sampled source,1.2V preamp bias, ideal reset pulses; reference conditions specified separately.' if cdac else 'Nominal3.3V25C, fixed10mV differential preamp input,1.2V bias, ideal references/reset pulses.'),
  ('Area-only plate capacitors feed preamp inputs through ideal sampling switches; no bootstrap error, coupling matrix or capacitor mismatch.' if cdac else 'Array loading is assigned area-only capacitance to ground; no capacitor feedback to analog input. This tests control circulation, not SAR conversion accuracy.'),
  (f'References use100pF each,{reference_r}ohm feedback clipped+/-150uA after ideal-assisted precharge until4ns; no buffer bandwidth,ESR/ESL or startup claim.' if finite else 'References ideal.'),
  'No wire parasitics, noise, mismatch, package, actual pulse-generator waveform or setup/hold qualification.']),indent=2))
