#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main(output2=False):
 W=R/('scratch/transceiver-reference-hybrid-output2-step' if output2 else 'scratch/transceiver-reference-hybrid-step')
 parent_directory=R/('scratch/transceiver-reference-output2-impedance' if output2 else 'scratch/transceiver-reference-hybrid-impedance')
 report_name='reference-hybrid-output2-step.json' if output2 else 'reference-hybrid-step.json'
 out=dict(status='pending',completed=False,cases=[])
 if (W/'result.json').exists():
  r=json.loads((W/'result.json').read_text());assert {(c['rail'],c['sign']) for c in r['cases']}=={(rail,sign) for rail in ('h','l') for sign in (-1,1)}
  for c in r['cases']:
   n=c['name'];assert c['sources_before']==c['sources_after']
   parent=parent_directory/('hybrid_'+c['rail']+'.spice')
   assert sha(parent)==c['parent_sha256']
   node='OH' if c['rail']=='h' else 'OL'
   pulse=f"ILOAD {node} 0 PWL(0n 0 20n 0 20.1n {c['sign']*.001} 30n {c['sign']*.001} 30.1n 0 100n 0)"
   body=(W/(n+'.spice')).read_text().split('.control')[0]
   assert body.replace(pulse,f'ILOAD {node} 0 DC 0 AC 1')==parent.read_text().split('.control')[0]
   for ext,h in c['artifacts_sha256'].items():assert sha(W/(n+ext))==h
   log=(W/(n+'.log')).read_text().lower();row=dict(name=n,completed=False,returncode=c['returncode'],artifacts_sha256=c['artifacts_sha256']);out['cases'].append(row)
   if c['returncode']!=0 or any(x in log for x in ('aborted','error','warning')):continue
   with (W/(n+'.dat')).open() as f:h=f.readline().lower().split()
   a=np.loadtxt(W/(n+'.dat'),skiprows=1);t=a[:,0];assert h==['time','v(oh)','v(ol)','i(vdd)','v(xdut.xhigh.x)','v(xdut.xlow.x)'] and a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(t)>0)
   if t[-1]+1e-21<100e-9:continue
   y=a[:,h.index('v(o'+c['rail']+')')];initial=float(np.mean(y[(t>=10e-9)&(t<=19e-9)]));error=y-initial;active=(t>=20e-9)&(t<=30.1e-9);post=(t>30.1e-9)
   row.update(completed=True,pre_pulse_voltage_v=initial,pulse_min_delta_v=float(error[active].min()),pulse_max_delta_v=float(error[active].max()),post_pulse_min_delta_v=float(error[post].min()),post_pulse_max_delta_v=float(error[post].max()),recovery_windows=[])
   for lo,hi in [(40,50),(60,70),(80,90),(95,100)]:
    mask=(t>=lo*1e-9)&(t<=hi*1e-9);assert mask.any();row['recovery_windows'].append(dict(window_ns=[lo,hi],max_absolute_delta_v=float(abs(error[mask]).max())))
  out['status']='terminal';out['completed']=all(c['completed'] for c in out['cases'])
 out['limitations']=['Relative to pre-pulse output, not ideal reference target; static offset retained.','Isolated1mA pulse does not reproduce full switched-CDAC charge, voltage dependence or periodic history.','Recovery windows are diagnostic; no settling threshold or stability guarantee.']
 (P/'evidence'/report_name).write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'])
 for c in out['cases']:
  if c['completed']:print(c['name'],c['pulse_min_delta_v'],c['pulse_max_delta_v'],c['recovery_windows'])

if __name__=='__main__':main()
