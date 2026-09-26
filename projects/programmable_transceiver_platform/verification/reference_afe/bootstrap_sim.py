"""Conditional reference bootstrap replay; not full ADC or oxide-reliability signoff.
Usage: python bootstrap_sim.py RAW_BULK_VOLTAGE_CLASS_EXTRACTION.json MODELDIR [figure7-low|figure7-high|figure7-loaded|figure7-refined] [SAMPLES]
"""
import hashlib,json,subprocess,sys,tempfile
from pathlib import Path
import numpy as np
source=Path(sys.argv[1]);models=Path(sys.argv[2]).resolve();j=json.loads(source.read_text())
assert j['cell']=='adc_bootsw_debug5'
selection=sys.argv[3] if len(sys.argv)>3 else None
figure_mode=selection is not None
assert selection in [None,'figure7-low','figure7-high','figure7-loaded','figure7-refined']
sample_hz=10e6 if figure_mode else 20e6
sample_count=int(sys.argv[4]) if figure_mode and len(sys.argv)>4 else 256
assert sample_count in [128,256,512,1024]
tone_bin=sample_count//2-1 if figure_mode else 63
def net(n):return n.replace('$','n_')
branches=[]
for suffix in ['p','n']:
 switches=[d for d in j['devices'] if d['type']=='nmos' and {d['terminals'][k] for k in ['S','D']}=={f'i_in{suffix}',f'o_out{suffix}'}]
 assert len(switches)==12
 gate=switches[0]['terminals']['G'];assert all(d['terminals']['G']==gate for d in switches)
 charge=[d for d in j['devices'] if d['type']=='pmos6' and d['terminals']['G']==gate and 'vdd' in [d['terminals']['S'],d['terminals']['D']]]
 assert len(charge)==1
 top=next(charge[0]['terminals'][k] for k in ['S','D'] if charge[0]['terminals'][k]!='vdd')
 branches.append(dict(suffix=suffix,gate=gate,bootstrap_top=top,total_sampling_width_um=sum(d['parameters']['W'] for d in switches)))
def circuit(positive,negative,body_case,load_pf=.666):
 lines=['Conditional bootstrap replay','.include design.ngspice','.lib sm141064.ngspice typical','.temp 25',
   'VDD vdd 0 3.3','VSS vss 0 0',f'VIP i_inp 0 {positive}',f'VIN i_inn 0 {negative}',
   f'VCK i_p_samp 0 PULSE(0 3.3 5n .1n .1n 15n {1/sample_hz})',f'CP o_outp 0 {load_pf}p',f'CN o_outn 0 {load_pf}p',
   '.options reltol=1e-6 abstol=1e-13']
 for i,d in enumerate(j['devices']):
  t=d['terminals'];p=d['parameters'];ty=d['type']
  if ty in ['nmos','nmos6','pmos6']:
   body=t['B'];model=ty[:4]+('_6p0' if ty.endswith('6') else '_3p3')
   if body_case!='extracted' and ty=='pmos6':
    for branch in branches:
     if {t['S'],t['D']}&{branch['gate'],branch['bootstrap_top']}:body=branch['bootstrap_top']
   lines.append(f"M{i} {net(t['D'])} {net(t['G'])} {net(t['S'])} {net(body)} {model} W={p['W']}u L={p['L']}u AD={p['AD']*1e-12} AS={p['AS']*1e-12} PD={p['PD']}u PS={p['PS']}u")
  elif ty=='mim_2ff':lines.append(f"C{i} {net(t['A'])} {net(t['B'])} {p['C']}")
  else:raise ValueError(ty)
 return lines

rows=[]
with tempfile.TemporaryDirectory(prefix='afe-bootstrap-') as td:
 for voltage,body_case,step in ([] if figure_mode else [(v,b,.1) for v in [.3,1.65,3.] for b in ['extracted','counterfactual_tracking_wells']]+[(3.,'extracted',.05)]):
  lines=circuit(str(voltage),str(3.3-voltage),body_case)
  out=Path(td)/'wave.txt';deck=Path(td)/'boot.cir'
  lines+=['.control','set num_threads=1','set wr_singlescale','set wr_vecnames','set numdgt=15',f'tran {step}n 250n 0 {step}n',
          f"wrdata {out} v(o_outp) v({net(branches[0]['gate'])}) v({net(branches[0]['bootstrap_top'])}) i(VDD)",'.endc','.end']
  deck.write_text('\n'.join(lines)+'\n')
  proc=subprocess.run(['ngspice','-b',str(deck)],cwd=models,capture_output=True,text=True,timeout=15)
  assert proc.returncode==0 and out.exists(),proc.stdout+proc.stderr
  a=np.loadtxt(out,skiprows=1)
  def at(t,column):return float(np.interp(t,a[:,0],a[:,column]))
  rows.append(dict(input_positive_v=voltage,body_case=body_case,max_step_ns=step,
   track_output_v=at(215e-9,1),track_error_v=at(215e-9,1)-voltage,
   track_gate_v=at(215e-9,2),track_gate_overdrive_v=at(215e-9,2)-voltage,
   bootstrap_top_v=at(215e-9,3),hold_output_v=at(240e-9,1),
   gate_peak_v=float(max(a[:,2]))))
if rows:
 base=next(r for r in rows if r['input_positive_v']==3 and r['body_case']=='extracted' and r['max_step_ns']==.1)
 assert abs(base['track_gate_v']-rows[-1]['track_gate_v'])<.005
 assert abs(base['track_output_v']-rows[-1]['track_output_v'])<1e-5
dynamic=[]
with tempfile.TemporaryDirectory(prefix='afe-bootstrap-dynamic-') as td:
 choices={'figure7-low':(.765,'extracted',.2,.666),'figure7-high':(1.5,'extracted',.2,.666),'figure7-loaded':(1.5,'extracted',.2,1.5),'figure7-refined':(1.5,'extracted',.1,.666)}
 for amplitude,body_case,step,load in ([choices[selection]] if figure_mode else [(1.5,'extracted',.2,.666),(1.5,'counterfactual_tracking_wells',.2,.666),(1.5,'extracted',.1,.666),(.5,'extracted',.2,.666),(1.5,'extracted',.2,1.5),(1.5,'extracted',.2,3.)]):
  frequency=sample_hz*tone_bin/sample_count
  lines=circuit(f'SIN(1.65 {amplitude} {frequency})',f'SIN(1.65 {amplitude} {frequency} 0 0 180)',body_case,load)
  out=Path(td)/'wave.txt';deck=Path(td)/'boot.cir'
  lines+=['.control','set num_threads=1','set wr_singlescale','set wr_vecnames','set numdgt=15',f'tran {step}n {(16+sample_count)/sample_hz} 0 {step}n',
          f'wrdata {out} v(o_outp) v(o_outn)','.endc','.end']
  deck.write_text('\n'.join(lines)+'\n')
  try:
   proc=subprocess.run(['ngspice','-b',str(deck)],cwd=models,capture_output=True,text=True,timeout=60)
  except subprocess.TimeoutExpired:
   print(json.dumps(dict(status='timed_out_no_spectral_result',timeout_s=60,selection=selection,samples=sample_count,sample_hz=sample_hz,input_hz=frequency,single_ended_peak_v=amplitude,output_load_pf=load,max_step_ns=step)))
   sys.exit(2)
  assert proc.returncode==0 and out.exists(),proc.stdout+proc.stderr
  a=np.loadtxt(out,skiprows=1);sample_times=(16+np.arange(sample_count))/sample_hz+40e-9
  positive=np.interp(sample_times,a[:,0],a[:,1]);negative=np.interp(sample_times,a[:,0],a[:,2])
  spectra={}
  for name,values in [('differential',positive-negative),('positive_only',positive)]:
   sp=abs(np.fft.rfft(values))*2/len(values);fundamental=float(sp[tone_bin]);sp[0]=0;sp[tone_bin]=0
   bins=[min((h*tone_bin)%sample_count,sample_count-(h*tone_bin)%sample_count) for h in [3,5,7]]
   spur_bin=int(np.argmax(sp))
   spectra[name]=dict(harmonics_3_5_7_dbc=[float(20*np.log10(max(sp[b],1e-30)/fundamental)) for b in bins],fundamental_peak_v=fundamental,sfdr_db=float(20*np.log10(fundamental/sp[spur_bin])),
                     deterministic_sndr_db=float(20*np.log10(fundamental/np.linalg.norm(sp))),largest_spur_bin=spur_bin)
  dynamic.append(dict(output_load_pf=load,single_ended_peak_v=amplitude,input_hz=frequency,body_case=body_case,max_step_ns=step,
                      sample_hz=sample_hz,samples=sample_count,hold_observation_ns=40,spectra=spectra))
  if figure_mode:dynamic[-1]['held_samples_v']={'positive':positive.tolist(),'negative':negative.tolist()}
if not figure_mode:assert abs(dynamic[0]['spectra']['differential']['sfdr_db']-dynamic[2]['spectra']['differential']['sfdr_db'])<.1
print(json.dumps(dict(selection=selection,analysis_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),source_gds_sha256=j['source_sha256'],raw_extraction_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
 model_sha256={n:hashlib.sha256((models/n).read_bytes()).hexdigest() for n in ['design.ngspice','sm141064.ngspice']},
 bootstrap_capacitors=[d for d in j['devices'] if d['type']=='mim_2ff'],branches=branches,extracted_bulk_audit=j['bulk_audit'],cases=rows,dynamic_sampling=dynamic,
 limitations=[f'Nominal PDK,25C,3.3V supply,{sample_hz}Hz assigned clock with15ns high phase. Figure7 mode matches annotated tone/rate approximately, not recovered input amplitude, acquisition duty or load.',
 'Assigned .666pF plate-only baseline and1.5/3pF sensitivity loads; no full capacitor matrix, reference switching, preamp, pads or package.',
 '3.3V versus6V gate classes extracted using Dualgate55/0; ideal2fF/um2 MIM and conductive wells.',
 'Counterfactual changes two PMOS bulk ties per branch to track bootstrap top; not the fabricated layout or an implementable fix without well/layout changes.',
 'Dynamic screen observes held analog differential samples, not ADC codes; no comparator, DAC switching, noise or quantization. Not measured ENOB or oxide reliability qualification.']),indent=2))
