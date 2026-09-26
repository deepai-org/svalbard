"""Conditional DC/AC replay of raw-finger opamp2 geometry (not calibrated PEX).
Usage: python amplifier_sim.py RAW_EXTRACTION.json PDK_MODEL_DIRECTORY
Requires ngspice and numpy; directory contains design.ngspice/sm141064.ngspice.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import numpy as np

source=Path(sys.argv[1]);models=Path(sys.argv[2]).resolve()
j=json.loads(source.read_text())
assert j['cell']=='opamp2_to_fix' and not j['disconnected_label_aliases']
assert len([d for d in j['devices'] if d['type']=='mim_2ff'])==8, 'Use --raw extraction'

def output_switch(d):
 return d['type'] in ['nmos','pmos'] and {d['terminals']['S'],d['terminals']['D']}=={'vout','vout_t'}

def net(n):return n.replace('$','n_')
def deck(vbn,vbp,load_pf,cap_scale,output_node,output):
 lines=['Conditional reference amplifier replay',f'.include "{models}/design.ngspice"',f'.lib "{models}/sm141064.ngspice" typical',
        '.temp 25','VDD vdd 0 3.3','VSS vss 0 0','VP vprog 0 1',f'VBN vbiasn 0 {vbn}',f'VBP vbiasp 0 {vbp}',
        'VIN vin2 0 1.65 AC 1',f'LFB {output_node} vin1 1e9','CAC vin1 0 1',f'CL {output_node} 0 {load_pf}p']
 for i,d in enumerate(j['devices']):
  t=d['terminals'];p=d['parameters']
  if d['type'] in ['nmos','pmos']:
   body=net(t.get('B') or ('vss' if d['type']=='nmos' else 'vdd'))
   lines.append(f"M{i} {net(t['D'])} {net(t['G'])} {net(t['S'])} {body} {d['type']}_3p3 W={p['W']}u L={p['L']}u AD={p['AD']*1e-12} AS={p['AS']*1e-12} PD={p['PD']}u PS={p['PS']}u")
  elif d['type']=='mim_2ff':lines.append(f"C{i} {net(t['A'])} {net(t['B'])} {p['C']*cap_scale}")
  else:raise ValueError('Unclassified device: '+d['type'])
 probes=[f'@m{i}[{param}]' for i,d in enumerate(j['devices']) if d['type'] in ['nmos','pmos'] and (d['terminals']['G'] in ['vbiasn','vbiasp'] or output_switch(d)) for param in ['gm','gds','vds','vdsat','id']]
 lines+=['.control','set wr_singlescale','set wr_vecnames','op',f'print v({output_node}) i(VDD)','print '+' '.join(probes),'ac dec 40 1 1e9',f'let gain=v({output_node})',f'wrdata {output} gain','.endc','.end']
 return '\n'.join(lines)+'\n'

rows=[]
with tempfile.TemporaryDirectory(prefix='reference-amp-') as td:
 for bn,bp,load,scale,output_node in ([(*case,'vout') for case in ([(bn,bp,1,1) for bn in [1.2,1.5,1.8] for bp in [1.2,1.5,1.8]]
                          +[(1.5,1.5,load,1) for load in [5,20]]
                          +[(1.5,1.5,1,scale) for scale in [.9,1.1,1.5,2]])]
                          +[(1.5,1.5,load,1,'vout_t') for load in [1,5,20]]
                          +[(1.5,1.5,load,scale,'vout_t') for load in [1,20] for scale in [.5,.75]]):
  run=Path(td);cir=run/'run.cir';ac=run/'ac.txt'
  cir.write_text(deck(bn,bp,load,scale,output_node,ac));ac.unlink(missing_ok=True)
  proc=subprocess.run(['ngspice','-b',str(cir)],cwd=models,capture_output=True,text=True,timeout=20)
  log=proc.stdout+proc.stderr
  row=dict(output_node=output_node,vbiasn_v=bn,vbiasp_v=bp,load_pf=load,compensation_scale=scale,assigned_mim_density_ff_per_um2=2*scale,exit_code=proc.returncode)
  if not ac.exists():
   row.update(status='simulation_failed',log_tail=log[-1500:]);rows.append(row);continue
  data=np.loadtxt(ac,skiprows=1);gain=np.hypot(data[:,1],data[:,2]);phase=np.unwrap(np.angle(data[:,1]+1j*data[:,2]))
  def val(name):return float(re.search(re.escape(name)+r'\s*=\s*([-+\deE.]+)',log,re.I).group(1))
  vout=val(f'v({output_node})');current=-val('i(vdd)')
  crossing=np.where((gain[:-1]>=1)&(gain[1:]<1))[0]
  unity=None;pm=None
  if len(crossing):
   i=int(crossing[0]);fraction=-np.log(gain[i])/(np.log(gain[i+1])-np.log(gain[i]))
   unity=float(np.exp(np.log(data[i,0])+fraction*np.log(data[i+1,0]/data[i,0])))
   pm=float(180+np.degrees(phase[i]+fraction*(phase[i+1]-phase[i])))
  row['output_switch_dc_incremental_r_ohm']=1/sum(val(f'@m{i}[gds]') for i,d in enumerate(j['devices']) if output_switch(d))
  row['cascode_fingers']=[dict(device=f'M{i}',type=d['type'],bias=d['terminals']['G'],
   **{param:val(f'@m{i}[{param}]') for param in ['gm','gds','vds','vdsat','id']})
   for i,d in enumerate(j['devices']) if d['type'] in ['nmos','pmos'] and d['terminals']['G'] in ['vbiasn','vbiasp']]
  row.update(status='conditional_operating_point' if abs(vout-1.65)<.01 else 'bias_not_centered',vout_v=vout,power_mw=current*3.3*1000,
             low_frequency_gain_db=float(20*np.log10(gain[0])),unity_gain_hz=unity,phase_margin_deg=pm,
             convergence_assistance=('gmin stepping' in log.lower()))
  rows.append(row)
reference=next(r for r in rows if r['vbiasn_v']==1.5 and r['vbiasp_v']==1.5 and r['load_pf']==1 and r['compensation_scale']==1 and r['output_node']=='vout_t')
ron=reference['output_switch_dc_incremental_r_ohm']
switches=[d for d in j['devices'] if output_switch(d)]
width=sum(d['parameters']['W'] for d in switches)
gate_area=sum(d['parameters']['W']*d['parameters']['L'] for d in switches)
assert all(math.isclose(d['parameters']['L'],.28,abs_tol=1e-12) for d in switches)
scaling=[dict(target_r_ohm=target,width_scale=ron/target,total_width_um=width*ron/target,
             nominal_gate_oxide_cap_f=gate_area*4.4e-15*ron/target) for target in [50,10,5]]
print(json.dumps(dict(output_switch_scaling=dict(reference_total_width_um=width,reference_length_um=.28,
 reference_ron_ohm=ron,cases=scaling,
 assumption='Ideal inverse-width resistance scaling at the same bias and geometry ratios; oxide area capacitance only, not measured RF port capacitance. No junction, overlap, interconnect or well parasitics.'),bulk_audit=j.get('bulk_audit'),source_gds_sha256=j['source_sha256'],raw_extraction_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
 model_sha256={n:hashlib.sha256((models/n).read_bytes()).hexdigest() for n in ['design.ngspice','sm141064.ngspice']},
 simulator=subprocess.run(['ngspice','--version'],capture_output=True,text=True).stdout.splitlines()[:4],cases=rows,
 assumptions=['Nominal process,25C,3.3V,Vprog=1V,input common mode=1.65V.',
 ('Bulk terminals taken from generic well/tap extraction; ideal well conductivity.' if all('B' in d['terminals'] for d in j['devices'] if d['type'] in ['nmos','pmos']) else 'NMOS bodies tied to VSS, PMOS to VDD; bulk connectivity not extracted.'),
 'Raw fingers retained, no manual device multiplier or gate-width regrouping.',
 'MIM base 2fF/um2 multiplied by compensation_scale; 0.5/0.75 test 1.0/1.5fF density options; 0.9..1.1 density scenarios, 1.5/2 diagnostic added-capacitance hypotheses. No routing/contact resistance or other interconnect capacitance.',
 'External cascode biases swept because exact bench voltages are not published.',
 'Ideal DC feedback holds output; AC loop opened. This does not test startup or closed-loop transient stability.',
 'Output load is at the selected node: internal vout or external-facing vout_t after the extracted transmission gate. Pad ESD/parasitics and package/test fixture not modeled.',
 'Agreement with a measured metric is not a unique physical calibration.']),indent=2))
