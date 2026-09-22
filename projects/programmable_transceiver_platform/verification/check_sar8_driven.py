#!/usr/bin/env python3
"""Verify the complete driver-to-decision connection and all eight trial updates."""
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];P=ROOT/'projects/programmable_transceiver_platform';W=ROOT/'scratch/transceiver-adc-sar8-driven';B=ROOT/'scratch/transceiver-adc-sar8-fast'
r=json.loads((W/'result.json').read_text())
for path,digest in r['source_sha256'].items():
 actual=P/'analog'/path.removeprefix('/screen/') if path.startswith('/screen/') else ROOT/'ip/blocks/analog/wifi_80211b'/path.removeprefix('/wifi/')
 assert hashlib.sha256(actual.read_bytes()).hexdigest()==digest
extra='''.include /screen/adc/sample_driver_headroom.spice
VBUF VBUF 0 3.3
IBN VBUF BN 20u
IBP BP 0 20u
XBN BN BN 0 0 nfet_03v3 w=8u l=.5u
XBP BP BP VBUF VBUF pfet_03v3 w=8u l=.5u
XBPDRV GP IP BN BP VBUF 0 pt_sample_driver_headroom
XBNDRV GN IN BN BP VBUF 0 pt_sample_driver_headroom
'''
assert len(r['cases'])==4
for c in r['cases']:
 name=c['name'];vin=c['input_difference_v'];base=(B/f'vin{vin:g}.spice').read_text()
 assert hashlib.sha256(base.encode()).hexdigest()==c['baseline_deck_sha256']
 for suffix,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+suffix)).read_bytes()).hexdigest()==digest
 d=(W/(name+'.spice')).read_text();assert extra in d
 d=d.replace(extra,'').replace('RIP SP GP 1k','RIP SP IP 1k').replace('RIN SN GN 1k','RIN SN IN 1k').replace(' v(IP) v(IN) i(VBUF)','').replace(f'/work/{name}.dat',f'/work/vin{vin:g}.dat')
 if c['changing']:
  for source,node,sign in (('VIP','SP',1),('VIN','SN',-1)):
   final=1.65+sign*vin/2;initial=1.65-sign*vin/2
   d=d.replace(f'{source} {node} 0 PWL(0 {initial} 50n {initial} 50.1n {final})',f'{source} {node} 0 {final}')
 assert d==base
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==31 and np.isfinite(a).all() and a[-1,0]>=114.9e-9
 def win(lo,hi):return a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)]
 def logic(w,col):
  high=bool(w[:,col].min()>2.97);low=bool(w[:,col].max()<.33);assert high or low,f'{name}: unsettled logic column {col}';return int(high)
 def code(w):return sum(logic(w,8+i)*2**i for i in range(8))
 assert code(win(58,59))==128
 trial=128;steps=[]
 for bit,edge in zip(range(7,-1,-1),range(77,113,5)):
  before=win(edge-.5,edge-.2);after=win(edge+2.5,edge+2.8)
  assert code(before)==trial
  keep=logic(before,27);assert logic(before,26)==1-keep
  pre=win(edge-2.5,edge-2.2);residue=float(np.mean(pre[:,1]-pre[:,2]))
  retained=trial if keep else trial&~(1<<bit);expected=retained|(1<<(bit-1)) if bit else retained
  assert code(after)==expected
  assert sum(logic(after,16+i)*2**i for i in range(8))==(1<<(bit-1) if bit else 0)
  assert logic(after,7)==int(bit==0)
  steps.append(dict(bit=bit,pre_evaluation_residue_v=residue,keep=bool(keep),agrees_with_residue=keep==int(residue<0),code_after_update=expected));trial=expected
 final=win(114,114.8);assert code(final)==c['final_code']==trial and logic(final,7)==1
 c['steps']=steps;c['final_residue_v']=float(np.mean(final[:,1]-final[:,2]));c['pre_conversion_held_value_v']=float(np.mean(win(64,64.8)[:,1]-win(64,64.8)[:,2]))
 c['ideal_capacitor_quantizer_code']=int(np.clip(np.floor(128-vin/(2/256)),0,255))
 c['buffer_current_during_conversion_ma']=float(-np.mean(a[(a[:,0]>=75e-9)&(a[:,0]<=114e-9),30])*1e3)
for c in r['cases']:
 if c['changing']:
  control=next(x for x in r['cases'] if not x['changing'] and x['input_difference_v']==c['input_difference_v'])
  c['change_minus_constant_code']=c['final_code']-control['final_code']
r['all_decision_capture_and_token_advances_checked']=True;r['all_comparator_decisions_agree_with_residue']=all(s['agrees_with_residue'] for c in r['cases'] for s in c['steps']);r['sample_rate_qualified']=False
(P/'evidence/adc-sar8-driven-screen.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps([{k:v for k,v in c.items() if k not in ('steps','artifacts_sha256','baseline_deck_sha256')} for c in r['cases']],indent=2))
