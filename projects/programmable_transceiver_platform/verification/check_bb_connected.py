#!/usr/bin/env python3
import hashlib,json,sys
SETTLING="--settling" in sys.argv
BYPASS="--bypass" in sys.argv
LEVEL10="--level10" in sys.argv
assert not LEVEL10 or BYPASS
assert not BYPASS or SETTLING
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/('scratch/transceiver-bb-connected-level10' if LEVEL10 else 'scratch/transceiver-bb-connected-bypass' if BYPASS else 'scratch/transceiver-bb-connected-settling' if SETTLING else 'scratch/transceiver-bb-connected');B=R/'scratch/transceiver-quadrature-lna-final'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());assert m.get('settling',False)==SETTLING;assert m.get('bypass',False)==BYPASS;assert m.get('level10',False)==LEVEL10;out=dict(status='pending',completed=False,cases=[],limitations=['Seeded/prebiased RF, actual two filters; ideal supplies/bias/passives and no ADC load.','Finite histories cannot establish stability, startup, noise, distortion or application bandwidth.'])
record=W/('result.json' if (W/'result.json').exists() else 'progress.json')
if record.exists():
 r=json.loads(record.read_text());terminal=record.name=='result.json'
 if terminal:assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 out.update(status='terminal' if terminal else 'partial_case_record',provenance=r)
 assert [c['name'] for c in r['cases']]==['zero','tone'][:len(r['cases'])]
 for c in r['cases']:
  name=c['name']
  if LEVEL10 and name=='zero':
   retained=R/'scratch/transceiver-bb-connected-bypass'
   prior=json.loads((retained/'result.json').read_text());assert prior['source_sha256_before']==m['source_sha256_before']==prior['source_sha256_after']
   original=next(x for x in prior['cases'] if x['name']=='zero')
   assert c['reused_zero'] and original['artifacts_sha256']==c['artifacts_sha256']
   for ext,h in original['artifacts_sha256'].items():assert sha(retained/(name+ext))==h
  assert sha(B/(name+'.spice'))==m['baseline_deck_sha256'][name]
  for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
  assert sha(W/(name+'.spice'))==c['deck_sha256_before']
  d=(W/(name+'.spice')).read_text()
  if LEVEL10 and name=='tone':
   assert c['amplitude_v']==.01 and d.count('VRF RFS 0 SIN(0 0.01 2.51542263g)')==1
   d=d.replace('VRF RFS 0 SIN(0 0.01 2.51542263g)','VRF RFS 0 SIN(0 0.001 2.51542263g)')
  if BYPASS:
   for n in (256,128,64):
    line=f'XCSB{n} LS 0 pt_ref_reservoir_{n}\n';assert d.count(line)==1;d=d.replace(line,'')
  if SETTLING:
   assert d.count('tran 2p 401n 0 2p uic')==1;d=d.replace('tran 2p 401n 0 2p uic','tran 2p 201n 0 2p uic')
  for line in ('.include /screen/bb_filter_section.spice','VBB BBVDD 0 3.3','VBBIAS BBBIAS 0 2.25','XFI MIP MIN FIP FIN BBBIAS BBVDD 0 pt_bb_filter RFB=20k C=20p','XFQ MQP MQN FQP FQN BBBIAS BBVDD 0 pt_bb_filter RFB=20k C=20p'):
   assert d.count(line+'\n')==1;d=d.replace(line+'\n','')
  assert d.replace(' v(FIP) v(FIN) v(FQP) v(FQN) i(VBB) i(VBBIAS)','')==(B/(name+'.spice')).read_text()
  row=dict(name=name,completed=False)
  f=W/(name+'.dat')
  if f.exists():
   with f.open() as stream:header=stream.readline().lower().split()
   with (B/(name+'.dat')).open() as stream:oldheader=stream.readline().lower().split()
   assert header==oldheader+['v(fip)','v(fin)','v(fqp)','v(fqn)','i(vbb)','i(vbbias)']
   a=np.loadtxt(f,skiprows=1);assert a.shape[1]==36 and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
   row.update(actual_stop_ns=float(a[-1,0]*1e9),completed=bool(c['returncode']==0 and not c['timed_out'] and a[-1,0]+1e-21>=(401e-9 if SETTLING else 201e-9) and 'aborted' not in (W/(name+'.log')).read_text().lower()))
   if row['completed']:
    row['windows']=[]
    for lo,hi in (((40,120),(120,200),(240,320),(320,400)) if SETTLING else ((40,120),(120,200))):
     w=a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)];t=w[:,0]
     def v(n):return w[:,header.index('v('+n.lower()+')')]
     record=dict(window_ns=[lo,hi],nodes={n:dict(mean_v=float(np.trapezoid(v(n),t)/(t[-1]-t[0])),range_v=[float(v(n).min()),float(v(n).max())]) for n in ('LG','LS','RF','MIP','MIN','MQP','MQN','FIP','FIN','FQP','FQN')},filter_supply_power_w=float(np.trapezoid(-3.3*w[:,header.index('i(vbb)')],t)/(t[-1]-t[0])))
     if BYPASS:
      record['selected_lna_finger_minimum_vds_margin_v']=float(np.min(w[:,header.index('@m.xlna.x1.m0[vds]')]-w[:,header.index('@m.xlna.x1.m0[vdsat]')]))
      record['source_power_w']={n:float(np.trapezoid(-3.3*w[:,header.index('i('+n+')')],t)/(t[-1]-t[0])) for n in ('vlna','vbuf','vpll','vbb')}
     row['windows'].append(record)
  out['cases'].append(row)
 out['completed']=terminal and len(out['cases'])==2 and all(c['completed'] for c in out['cases'])
(P/('evidence/bb-connected-level10.json' if LEVEL10 else 'evidence/bb-connected-bypass.json' if BYPASS else 'evidence/bb-connected-settling.json' if SETTLING else 'evidence/bb-connected.json')).write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'])
