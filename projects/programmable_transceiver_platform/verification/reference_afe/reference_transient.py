"""Recovered MSB driver with conditional finite reference sources and reservoirs.
Usage: python reference_transient.py RAW_MSB_EXTRACTION.json MODELDIR [rising|falling] [EDGE_NS] [REFERENCE_SPAN_V] [BIT_LABEL]
Bodies follow the separately traced complete ADC parent, not local unnamed nets.
"""
import hashlib,json,subprocess,sys,tempfile
from pathlib import Path
import numpy as np
from scipy.integrate import trapezoid
source=Path(sys.argv[1]);models=Path(sys.argv[2]).resolve();j=json.loads(source.read_text())
expected_width={'lib_dac_sw_msb':32,'lib_dac_sw':8}[j['cell']]
assert sum(d['parameters']['W'] for d in j['devices'] if d['type']=='nmos')==expected_width
assert sum(d['parameters']['W'] for d in j['devices'] if d['type']=='pmos')==2*expected_width
falling=len(sys.argv)>3 and sys.argv[3]=="falling"
edge_ns=float(sys.argv[4]) if len(sys.argv)>4 else .2
assert 0<edge_ns<=2
span=float(sys.argv[5]) if len(sys.argv)>5 else 1.7
assert 0<span<3.3
high=1.65+span/2;low=1.65-span/2
target=low if falling else high
rail_column=3 if falling else 2
bit_label=sys.argv[6] if len(sys.argv)>6 else None
cb_pf=cr_pf=.75
geometry_hash=None
if bit_label:
 geometry_path=Path(__file__).resolve().parents[2]/'evidence/reference-afe-cap-geometry.json'
 geometry=json.loads(geometry_path.read_text())
 weights={b:g['m3_m4_overlap_um2']*.0394e-3 for b,g in geometry['bit_geometry'].items()}
 cb_pf=weights[bit_label];cr_pf=sum(weights.values())-cb_pf
 geometry_hash=hashlib.sha256(geometry_path.read_bytes()).hexdigest()
rows=[]
with tempfile.TemporaryDirectory(prefix='afe-reference-') as td:
 cases=[('floating',100,True,.02)]+[(common,cap,False,.02) for common in ['floating','clamped'] for cap in [10,100,1000]]
 cases += [('floating',100,False,.01),('clamped',100,False,.01)]
 for common,reservoir,ideal,step_ns in cases:
  lines=['Conditional MSB reference replay','.include design.ngspice','.lib sm141064.ngspice typical','.temp 25',
   'VDD vdd 0 3.3','VSS vss 0 0',f'VG in 0 PULSE(3.3 0 5n {edge_ns}n {edge_ns}n 20n 100n)',
   f'CB out common {cb_pf}p',f'CR common 0 {cr_pf}p',
   'VCM common 0 1.65' if common=='clamped' else 'RBIAS common bias 1e12',
   'VBIAS bias 0 1.65',f'CP vrefp 0 {reservoir}p',f'CN vrefn 0 {reservoir}p',
   '.options reltol=1e-6 abstol=1e-13 vntol=1e-9']
  if falling:lines=[s.replace('PULSE(3.3 0','PULSE(0 3.3') for s in lines]
  if ideal:lines+=[f'VRP vrefp 0 {high}',f'VRN vrefn 0 {low}']
  else:lines+=[f'BRP 0 vrefp I=min(max(({high}-v(vrefp))/10,-150u),150u)',
               f'BRN 0 vrefn I=min(max(({low}-v(vrefn))/10,-150u),150u)']
  for i,d in enumerate(j['devices']):
   t=d['terminals'];p=d['parameters'];ty=d['type'];assert ty in ['nmos','pmos']
   body='vss' if ty=='nmos' else 'vdd'
   lines.append(f"M{i} {t['D']} {t['G']} {t['S']} {body} {ty}_3p3 W={p['W']}u L={p['L']}u AD={p['AD']*1e-12} AS={p['AS']*1e-12} PD={p['PD']}u PS={p['PS']}u")
  out=Path(td)/'wave.txt';deck=Path(td)/'ref.cir'
  terminal_vectors=' i(vg) i(vdd) i(vss) i(vbias)'+(' i(vcm)' if common=='clamped' else '')
  lines+=['.control','set wr_singlescale','set wr_vecnames','set numdgt=15',f'tran {step_ns}n 50n 0 {step_ns}n',
          f'wrdata {out} v(out) v(vrefp) v(vrefn) v(common){terminal_vectors}','.endc','.end']
  deck.write_text('\n'.join(lines)+'\n')
  proc=subprocess.run(['ngspice','-b',str(deck)],cwd=models,capture_output=True,text=True,timeout=20)
  assert proc.returncode==0 and out.exists(),proc.stdout+proc.stderr
  a=np.loadtxt(out,skiprows=1);window=(a[:,0]>=5e-9)&(a[:,0]<25e-9)
  errors=[]
  for ns in [1,3,10]:
   time=(5+edge_ns+ns)*1e-9
   output=np.interp(time,a[:,0],a[:,1]);rail=np.interp(time,a[:,0],a[:,rail_column])
   errors.append(dict(ns_after_gate_edge=ns,output_error_mv=float((output-target)*1000),
                     reference_error_mv=float((rail-target)*1000),switch_error_mv=float((output-rail)*1000)))
  reference_charge={}
  terminal_charge={}
  if not ideal:
   # First transition only, ending before the gate returns. Positive charge
   # leaves the reservoir/source node toward the recovered switch network.
   times=np.r_[5e-9,a[(a[:,0]>5e-9)&(a[:,0]<20e-9),0],20e-9]
   for name,column,voltage in [('high',2,high),('low',3,low)]:
    rail=np.interp(times,a[:,0],a[:,column])
    current=np.clip((voltage-rail)/10,-150e-6,150e-6)
    supplied=trapezoid(current,times)
    stored=reservoir*1e-12*(rail[-1]-rail[0])
    reference_charge[name]=dict(source_charge_pc=float(supplied*1e12),
      reservoir_charge_change_pc=float(stored*1e12),
      net_charge_to_switch_network_pc=float((supplied-stored)*1e12))
   # SPICE voltage-source current is into its positive terminal; negate
   # to report charge delivered to the network. Include the clamping source.
   names=['gate','pmos_body','nmos_body','bias']+(['common_clamp'] if common=='clamped' else [])
   for column,name in enumerate(names,5):
    terminal_charge[name]=float(-trapezoid(np.interp(times,a[:,0],a[:,column]),times)*1e12)
   common_voltage=np.interp(times,a[:,0],a[:,4])
   ground_cap_delta_pc=cr_pf*(common_voltage[-1]-common_voltage[0])
   total=sum(terminal_charge.values())+sum(q['net_charge_to_switch_network_pc'] for q in reference_charge.values())
   terminal_charge['ground_capacitor_charge_change_pc']=float(ground_cap_delta_pc)
   terminal_charge['charge_balance_residual_pc']=float(total-ground_cap_delta_pc)
   assert abs(total-ground_cap_delta_pc)<.001,terminal_charge
  rows.append(dict(bit_label=bit_label,switched_capacitance_pf=cb_pf,remaining_capacitance_pf=cr_pf,reference_span_v=span,terminal_charge_5_to_20ns_pc=terminal_charge,gate_edge_ns=edge_ns,reference_charge_5_to_20ns=reference_charge,transition='high_to_low' if falling else 'low_to_high',maximum_low_reference_rise_mv=float((max(a[window,3])-low)*1000),maximum_timestep_ns=step_ns,common_node=common,reservoir_per_rail_pf=reservoir,ideal_reference=ideal,
      maximum_high_reference_droop_mv=float((high-min(a[window,2]))*1000),settling=errors))
assert abs(rows[0]['settling'][0]['output_error_mv'])<.1
refinements=[]
for fine in rows[-2:]:
 coarse=next(r for r in rows[:-2] if r['common_node']==fine['common_node'] and r['reservoir_per_rail_pf']==100 and not r['ideal_reference'])
 difference=max(abs(a['output_error_mv']-b['output_error_mv']) for a,b in zip(coarse['settling'],fine['settling']))
 metric='maximum_low_reference_rise_mv' if falling else 'maximum_high_reference_droop_mv'
 droop_difference=abs(coarse[metric]-fine[metric])
 assert difference<.01 and droop_difference<.1,(difference,droop_difference)
 charge_difference=max(abs(fine['reference_charge_5_to_20ns'][rail]['net_charge_to_switch_network_pc']-coarse['reference_charge_5_to_20ns'][rail]['net_charge_to_switch_network_pc']) for rail in ['high','low'])
 assert charge_difference<.001,charge_difference
 refinements.append(dict(maximum_reference_charge_difference_pc=charge_difference,common_node=fine['common_node'],maximum_sampled_output_difference_mv=difference,maximum_droop_difference_mv=droop_difference))
print(json.dumps(dict(driver_cell=j['cell'],cap_geometry_sha256=geometry_hash,analysis_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),timestep_refinement=refinements,source_gds_sha256=j['source_sha256'],raw_extraction_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
 model_sha256={n:hashlib.sha256((models/n).read_bytes()).hexdigest() for n in ['design.ngspice','sm141064.ngspice']},
 cases=rows,assumptions=[f'Nominal PDK,25C,VDD3.3V,reference{high}/{low}V,{edge_ns}ns gate edges.',
 f'Switched{cb_pf}pF plus remaining{cr_pf}pF, common node floating or ideal clamped. Optional bit label uses area-only geometry weights; no full matrix or other transitions.',
 'Finite references are ideal10ohm feedback sources clipped to+/-150uA with assigned local reservoirs. Not characterized source circuits; no delay, ESR, ESL or package.',
 'Switch body rails are established by full-parent reference_drivers.py; local child body labels alone are insufficient.',
 'Terminal-current integral uses positive charge delivered by each voltage source. Reference source integrals subtract reservoir storage; total terminal charge closes against the grounded remaining-array capacitor. This is a numerical KCL check, not silicon calibration.',
 'One switched edge identifies settling mechanisms, not full ADC error, reference-loop stability or RF qualification.']),indent=2))
