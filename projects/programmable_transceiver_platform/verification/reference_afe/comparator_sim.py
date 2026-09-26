"""Conditional comparator replay; not ADC qualification or a noise simulation.
Usage: python comparator_sim.py RAW_COMPARATOR.json MODELDIR [RAW_PREAMP.json] [common-mode]
Parent tracing establishes joined VDD islands and joined $6/$8 calibration gates.
Calibration gates held at VDD represent settled pad_offcal_en=0 NAND state.
Published calibration enable/bias settings and dynamic timing remain unknown.
"""
import hashlib,json,subprocess,sys,tempfile
from pathlib import Path
import numpy as np
source=Path(sys.argv[1]);models=Path(sys.argv[2]).resolve();j=json.loads(source.read_text())
assert j['cell']=='adc_comp_miyahara_offcal'
assert len(j['devices'])==97
preamp=json.loads(Path(sys.argv[3]).read_text()) if len(sys.argv)>3 else None
if preamp:assert preamp['cell']=='adc_preamp_v2'
common_mode_screen=len(sys.argv)>4 and sys.argv[4]=='common-mode'
if common_mode_screen:assert preamp is not None
rows=[]
with tempfile.TemporaryDirectory(prefix='afe-comparator-') as td:
 cases=[(d,c,0,0,0) for d in [-.1,-.01,-.001,.001,.01,.1] for c in [5,50]]
 cases += [(d,50,1000,c,asym) for d in [-.001,.001] for c in [20,100,500] for asym in [0,.1]]
 cases=[(*case,.005) for case in cases]
 cases += [(.001,50,1000,c,a,.0025) for c in [20,100] for a in [.1,-.1]]
 cases=[(*case,None) for case in cases]
 if preamp:cases=[(d,50,0,c,a,.005,bias) for d in [-.001,.001] for c in [20,100] for a in [0,.1] for bias in [.8,1.,1.2]]
 cases=[(*case,1.65) for case in cases]
 if common_mode_screen:
  cases=[(d,50,0,20,0,.005,bias,cm) for d in [-.001,.001] for bias in [.8,1.,1.2] for cm in [.735,.77,1.16,1.585,1.65]]
 for differential,load_ff,source_r,input_c,asymmetry,step_ns,bias,common_mode in cases:
   lines=['Conditional recovered comparator','.include design.ngspice','.lib sm141064.ngspice typical','.temp 25',
    'VDD vdd 0 3.3','VSS vss 0 0','VISO vdd__island2 vdd 0','VCAL1 cal1 0 3.3','VCAL2 cal2 cal1 0',
    'VCLK i_p_amplify 0 PULSE(0 3.3 3n .1n .1n 5n 10n)',
    f'VIP source_p 0 {common_mode+differential/2}',f'VIN source_n 0 {common_mode-differential/2}',
    f'CP o_outp 0 {load_ff}f',f'CN o_outn 0 {load_ff}f','.options reltol=1e-6 abstol=1e-13 vntol=1e-9']
   if preamp:
    lines += [f'VBIAS nbias 0 {bias}',f'CIP i_inp 0 {input_c}f',f'CIN i_inn 0 {input_c}f']
    def pn(n):return {'i_inp':'source_p','i_inn':'source_n','o_outp':'i_inp','o_outn':'i_inn','vdd':'vdd','vss':'vss','nbias':'nbias'}.get(n,'pre_'+n.replace('$','net_'))
    for idx,device in enumerate(preamp['devices']):
     t=device['terminals'];q=device['parameters']
     if device['type']=='resistor':
      side=1 if 'o_outp' in t.values() else -1
      lines.append(f"RP{idx} {pn(t['A'])} {pn(t['B'])} {q['R']*(1+side*asymmetry)}")
     else:
      assert device['type']=='nmos'
      lines.append(f"MP{idx} {' '.join(pn(t[n]) for n in ['D','G','S','B'])} nmos_3p3 W={q['W']}u L={q['L']}u AD={q['AD']*1e-12} AS={q['AS']*1e-12} PD={q['PD']}u PS={q['PS']}u")
   elif source_r:
    lines += [f'RIP source_p i_inp {source_r*(1+asymmetry)}',f'RIN source_n i_inn {source_r*(1-asymmetry)}',f'CIP i_inp 0 {input_c}f',f'CIN i_inn 0 {input_c}f']
   else:lines += ['VJP source_p i_inp 0','VJN source_n i_inn 0']
   def node(n):return {'$6':'cal1','$8':'cal2'}.get(n,n.replace('$','net_'))
   for i,d in enumerate(j['devices']):
    t=d['terminals'];p=d['parameters'];ty=d['type'];assert ty in ['nmos','pmos']
    lines.append(f"M{i} {' '.join(node(t[n]) for n in ['D','G','S','B'])} {ty}_3p3 W={p['W']}u L={p['L']}u AD={p['AD']*1e-12} AS={p['AS']*1e-12} PD={p['PD']}u PS={p['PS']}u")
   deck=Path(td)/'comp.cir';wave=Path(td)/'wave.txt'
   lines+=['.control','set num_threads=1','set wr_singlescale','set wr_vecnames','set numdgt=15',f'tran {step_ns}n 9n 0 {step_ns}n',f'wrdata {wave} v(o_outp) v(o_outn) v(x_sb) v(x_rb) v(i_inp) v(i_inn)','.endc','.end']
   deck.write_text('\n'.join(lines)+'\n');proc=subprocess.run(['ngspice','-b',str(deck)],cwd=models,capture_output=True,text=True,timeout=20)
   assert proc.returncode==0 and wave.exists(),proc.stdout+proc.stderr
   a=np.loadtxt(wave,skiprows=1);mask=(a[:,0]>=3.1e-9)&(a[:,0]<8e-9);b=a[mask]
   target=np.sign(differential);resolved=(b[:,1]*target-b[:,2]*target)>2.64
   indices=np.flatnonzero(resolved)
   edge=a[(a[:,0]>=3e-9)&(a[:,0]<8e-9)]
   baseline_p=float(np.interp(2.9e-9,a[:,0],a[:,5]));baseline_n=float(np.interp(2.9e-9,a[:,0],a[:,6]))
   rows.append(dict(preamp_bias_v=bias,preamp_load_fractional_asymmetry=asymmetry if preamp else None,
    comparator_input_common_mode_before_edge_v=(baseline_p+baseline_n)/2,comparator_input_differential_before_edge_v=baseline_p-baseline_n,maximum_timestep_ns=step_ns,source_resistance_ohm=source_r,input_capacitance_per_side_ff=input_c,source_resistance_fractional_asymmetry=asymmetry,
    peak_common_mode_input_disturbance_mv=float(np.max(np.abs((edge[:,5]+edge[:,6]-baseline_p-baseline_n)/2))*1000),
    peak_differential_input_disturbance_mv=float(np.max(np.abs(edge[:,5]-edge[:,6]-(baseline_p-baseline_n)))*1000),
    differential_input_v=differential,output_load_per_side_ff=load_ff,common_mode_v=common_mode,
    decision_ns_after_clock_edge=float((b[indices[0],0]-3.1e-9)*1e9) if len(indices) else None,
    output_difference_at_7ns_v=float(np.interp(7e-9,a[:,0],a[:,1]-a[:,2]))))
print(json.dumps(dict(analysis_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),common_mode_screen=common_mode_screen,preamp_raw_sha256=hashlib.sha256(Path(sys.argv[3]).read_bytes()).hexdigest() if preamp else None,source_gds_sha256=j['source_sha256'],raw_extraction_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
 model_sha256={n:hashlib.sha256((models/n).read_bytes()).hexdigest() for n in ['design.ngspice','sm141064.ngspice']},cases=rows,
 assumptions=['Nominal PDK25C3.3V; assigned5/50fF output loads. Inputs ideal or1kohm sources with assigned20/100/500fF shunts; +/-10% resistance asymmetry is sensitivity, not measured mismatch.',
 'Optional preamp uses recovered36NMOS fingers and20 assigned10kohm resistors; bias and load mismatch are scenarios. No resistor parasitics or measured bias. Disturbances referenced to pre-edge inputs.',
 'Parent connectivity joins VDD islands and calibration gates; calibration gates3.3V represent settled pad_offcal_en=0 NAND state; not recovered dynamic timing or measured enable setting.',
 'Decision threshold80%VDD differential after100ps clock rising edge; no extracted routing capacitance, transistor mismatch or noise. Finite source impedance approximates loading, not an actual preamp replay.',
 'Static input during one reset/evaluate cycle; does not establish consecutive decision recovery or silicon metastability probability.']),indent=2))
