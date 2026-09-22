#!/usr/bin/env python3
import hashlib,json,sys
LNA="--lna" in sys.argv
FINAL="--final-stage" in sys.argv
assert not FINAL or LNA
ACCOUPLED="--ac-coupled" in sys.argv
assert not ACCOUPLED or (LNA and FINAL)
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/('scratch/transceiver-quadrature-lna-ac' if ACCOUPLED else 'scratch/transceiver-quadrature-lna-final' if FINAL else 'scratch/transceiver-quadrature-lna' if LNA else 'scratch/transceiver-quadrature-mixers');B=R/'scratch/transceiver-quadrature-ring'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def edges(t,v):
 k=np.flatnonzero((v[:-1]<0)&(v[1:]>=0));return t[k]-v[k]*(t[k+1]-t[k])/(v[k+1]-v[k])
m=json.loads((W/'manifest.json').read_text());assert m.get('lna_mode',False)==LNA and m.get('final_stage',False)==FINAL and m.get('ac_coupled',False)==ACCOUPLED;assert sha(B/'a0.4.spice')==m['baseline_deck_sha256']
out=dict(completed=False,status='pending',cases=[],limitations=['Seeded ring and two mixers; ideal RF source/bias and output terminations, no LNA/ADC or PLL.','Completion and voltage ranges do not establish conversion quality; conversion/no-tone comparison still required.','Power excludes control/regeneration and common-mode source delivery.'])
record=W/('result.json' if (W/'result.json').exists() else 'progress.json')
if record.exists():
 r=json.loads(record.read_text());terminal=record.name=='result.json'
 if terminal:assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 out.update(status='terminal' if terminal else 'partial_case_record',provenance=r)
 assert [c['name'] for c in r['cases']]==['zero','tone'][:len(r['cases'])]
 for c in r['cases']:
  for ext,h in c['artifacts_sha256'].items():assert sha(W/(c['name']+ext))==h
  assert c['deck_sha256_before']==c['artifacts_sha256']['.spice']
  deck=(W/(c['name']+'.spice')).read_text();assert 'tran 2p 201n 0 2p uic' in deck
  # Remove exactly the declared added mixer fixture and output probes.
  additions=['.include /wifi/rf_switch_mixer/mixer.spice','RRF RFS RF 300','XMI RF OIP OIN MIP MIN 0 wifi_rf_switch_mixer','XMQ RF OQP OQN MQP MQN 0 wifi_rf_switch_mixer']+[f'R{n} {n} 0 1k' for n in ('MIP','MIN','MQP','MQN')]+[f'C{n} {n} 0 1p' for n in ('MIP','MIN','MQP','MQN')]+[f"VRF RFS 0 SIN(1.5 {c['amplitude_v']} 2.51542263g)"]
  restored=deck
  if ACCOUPLED:
   assert restored.count('XAC RF MRFIN pt_ref_reservoir_256\n')==1
   restored=restored.replace('XAC RF MRFIN pt_ref_reservoir_256\n','').replace('XMI MRFIN OIP','XMI RF OIP').replace('XMQ MRFIN OQP','XMQ RF OQP').replace(' v(MRFIN)','')
  if FINAL:
   line='.include /screen/quadrature/lo_final_stage.spice\n';assert restored.count(line)==1;restored=restored.replace(line,'')
   for node in ('IP','IN','QP','QN'):
    line=f'XF{node} PRE{node} O{node} VDD 0 pt_lo_final_stage\n';assert restored.count(line)==1;restored=restored.replace(line,'')
    line=f'XB{node} B{node} PRE{node} VDD 0 pt_lo_buffer';assert restored.count(line)==1;restored=restored.replace(line,f'XB{node} B{node} O{node} VDD 0 pt_lo_buffer')
  if LNA:
   lna='.include /wifi/rf_lna/lna_cs_core.spice\nVLNA LNAVDD 0 3.3\nVBIAS LBIAS 0 1.5\nRRF RFS LIN 50\nCCRF LIN LG 20p\nRB LG LBIAS 1meg\nRD LNAVDD RF 300\nRS LS 0 82\nXLNA LG RF LS 0 wifi_lna_cs_core\n.ic v(LG)=1.5\n'
   assert restored.count(lna)==1
   restored=restored.replace(lna,'RRF RFS RF 300\n').replace(f"VRF RFS 0 SIN(0 {c['amplitude_v']}",f"VRF RFS 0 SIN(1.5 {c['amplitude_v']}")
   restored=restored.replace(' v(LG) v(LS) v(LIN) i(VLNA) @m.xlna.x1.m0[vds] @m.xlna.x1.m0[vdsat] @m.xlna.x1.m0[id]','').replace('save all @m.xlna.x1.m0[vds] @m.xlna.x1.m0[vdsat] @m.xlna.x1.m0[id]\n','')
  for line in additions:assert restored.count(line+'\n')==1;restored=restored.replace(line+'\n','')
  restored=restored.replace('tran 2p 201n 0 2p uic','tran 2p 81n 0 2p uic').replace('/work/'+c['name']+'.dat','/work/a0.4.dat').replace(' v(RF) v(MIP) v(MIN) v(MQP) v(MQN) i(VRF)','')
  assert restored==(B/'a0.4.spice').read_text()
  row=dict(name=c['name'],completed=False)
  f=W/(c['name']+'.dat')
  if f.exists():
   with f.open() as stream:header=stream.readline().lower().split()
   assert header[17:23]==['v(rf)','v(mip)','v(min)','v(mqp)','v(mqn)','i(vrf)']
   a=np.loadtxt(f,skiprows=1);assert a.shape[1]==(31 if ACCOUPLED else 30 if LNA else 23) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
   row.update(actual_stop_ns=float(a[-1,0]*1e9),completed=bool(c['returncode']==0 and not c['timed_out'] and a[-1,0]+1e-21>=201e-9 and 'aborted' not in (W/(c['name']+'.log')).read_text().lower()))
   if row['completed']:
    w=a[(a[:,0]>=120e-9)&(a[:,0]<=200e-9)];t=w[:,0]
    def v(n):return w[:,header.index('v('+n.lower()+')')]
    e=edges(t,v('P')-v('N'));row['ring_frequency_hz']=float((len(e)-1)/(e[-1]-e[0])) if len(e)>2 else None
    row['late_ranges_v']={n:[float(v(n).min()),float(v(n).max())] for n in ('OIP','OIN','OQP','OQN','RF','MIP','MIN','MQP','MQN')}
    if ACCOUPLED:row['mixer_input_range_v']=[float(v('MRFIN').min()),float(v('MRFIN').max())]
    row['buffer_supply_power_w']=float(np.trapezoid(-3.3*w[:,header.index('i(vbuf)')],t)/(t[-1]-t[0]))
    row['ring_supply_power_w']=float(np.trapezoid(-3.3*w[:,header.index('i(vpll)')],t)/(t[-1]-t[0]))
    ei=edges(t,v('OIP')-v('OIN'));eq=edges(t,v('OQP')-v('OQN'));phase=[]
    if row['ring_frequency_hz']:
     period=1/row['ring_frequency_hz']
     for edge in ei:
      k=np.searchsorted(eq,edge)-1
      if k>=0 and edge-eq[k]<period:phase.append((edge-eq[k])/period*360)
    row['lo_q_lead_phase_deg_range']=[float(min(phase)),float(max(phase))] if phase else None
    if LNA:
     row['lna_gate_range_v']=[float(v('LG').min()),float(v('LG').max())]
     row['lna_source_range_v']=[float(v('LS').min()),float(v('LS').max())]
     vd=w[:,header.index('@m.xlna.x1.m0[vds]')];vs=w[:,header.index('@m.xlna.x1.m0[vdsat]')]
     row['representative_forward_finger_min_vds_minus_vdsat_v']=float((vd-vs).min())
     row['representative_forward_finger_negative_vds_samples']=int(np.sum(vd<0))
     row['lna_supply_power_w']=float(np.trapezoid(-3.3*w[:,header.index('i(vlna)')],t)/(t[-1]-t[0]))
  out['cases'].append(row)
 out['completed']=terminal and len(out['cases'])==2 and all(c['completed'] for c in out['cases'])
if LNA:out['limitations'][0]='Actual LNA with prebiased gate and seeded ring, I/Q mixers; ideal supplies/bias/passives; no ADC/PLL or cold startup. Only one forward-oriented LNA finger is device-probed.'
(P/('evidence/quadrature-lna-ac.json' if ACCOUPLED else 'evidence/quadrature-lna-final.json' if FINAL else 'evidence/quadrature-lna.json' if LNA else 'evidence/quadrature-mixers.json')).write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed']);print(out['cases'])
