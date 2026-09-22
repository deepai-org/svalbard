#!/usr/bin/env python3
"""Verify every comparator-driven trial, token advance and retained output code."""
import argparse,hashlib,json,re
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];P=ROOT/'projects/programmable_transceiver_platform';parser=argparse.ArgumentParser();parser.add_argument('--buffered',action='store_true');parser.add_argument('--fast',action='store_true');args=parser.parse_args();args.buffered=args.buffered or args.fast;tag='fast' if args.fast else ('buffered' if args.buffered else 'closed');W=ROOT/('scratch/transceiver-adc-sar8-'+tag)
r=json.loads((W/'result.json').read_text())
for path,digest in r['source_sha256'].items():
 actual=P/'analog'/path.removeprefix('/screen/') if path.startswith('/screen/') else ROOT/'ip/blocks/analog/wifi_80211b'/path.removeprefix('/wifi/')
 assert hashlib.sha256(actual.read_bytes()).hexdigest()==digest
assert len(r['cases'])==4
for c in r['cases']:
 name=c['name']
 for suffix,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+suffix)).read_bytes()).hexdigest()==digest
 deck=(W/(name+'.spice')).read_text()
 keep_node='KEEPN' if args.buffered else 'QN'
 assert f'XCTL {keep_node} UPDATE START RN D0 D1 D2 D3 D4 D5 D6 D7 DONE VLOG 0 pt_sar8_control' in deck
 if args.buffered:
  original=(ROOT/'scratch/transceiver-adc-sar8-closed'/(name+'.spice')).read_text()
  reverse=deck.replace('XCTL KEEPN UPDATE','XCTL QN UPDATE').replace(' v(KEEPP) v(KEEPN)','')
  for line in ('XOP0 QP QPB VLOG 0 pt_inv','XOP1 QPB KEEPP VLOG 0 pt_inv','XON0 QN QNB VLOG 0 pt_inv','XON1 QNB KEEPN VLOG 0 pt_inv'):
   assert line+'\n' in reverse;reverse=reverse.replace(line+'\n','')
  if args.fast:
   for prefix in ('VUPDATE UPDATE 0 ', 'VC CLK 0 ', 'tran '):
    original_line=next(line for line in original.splitlines() if line.startswith(prefix))
    reverse=re.sub('^'+re.escape(prefix)+'.+$',original_line,reverse,flags=re.M)
  assert reverse==original
 assert not any(line.startswith('VD'+str(i)+' ') for line in deck.splitlines() for i in range(8))
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==(28 if args.buffered else 26) and np.isfinite(a).all() and a[-1,0]>=(114.9e-9 if args.fast else 274e-9)
 def win(lo,hi):return a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)]
 def logic(w,col):
  assert w.shape[0]>0
  high=bool(w[:,col].min()>2.97);low=bool(w[:,col].max()<.33)
  assert high or low, f'{name}: logic level not stable at column {col}'
  return int(high)
 def code(w):return sum(logic(w,8+i)*2**i for i in range(8))
 assert code(win(58,59))==128,'Sampling baseline must be midcode'
 assert sum(logic(win(58,59),16+i)*2**i for i in range(8))==128
 trial=128;steps=[]
 for bit,edge in zip(range(7,-1,-1),(range(77,113,5) if args.fast else range(80,256,25))):
  before=win(edge-.5,edge-.2) if args.fast else win(edge-1,edge-.5);after=win(edge+2.5,edge+2.8) if args.fast else win(edge+3,edge+4)
  assert code(before)==trial
  keep=logic(before,27 if args.buffered else 4);assert logic(before,26 if args.buffered else 3)==1-keep
  residue=win(edge-2.5,edge-2.2) if args.fast else win(edge-5.5,edge-5.2);residual=float(np.mean(residue[:,1]-residue[:,2]))
  analog_correct=keep==int(residual<0)
  retained=trial if keep else trial & ~(1<<bit)
  expected=retained | (1<<(bit-1)) if bit else retained
  assert code(after)==expected,f'{name}: stored decision or next trial incorrect at bit {bit}'
  settling=win(edge,edge+(2.8 if args.fast else 4))
  valid=np.ones(len(settling),dtype=bool)
  for i in range(8):valid &= (settling[:,8+i]>2.97) if ((expected>>i)&1) else (settling[:,8+i]<.33)
  stable=np.flatnonzero(np.logical_and.accumulate(valid[::-1])[::-1]);assert len(stable)
  settled_after_ns=float(settling[stable[0],0]*1e9-edge)
  expected_token=1<<(bit-1) if bit else 0
  assert sum(logic(after,16+i)*2**i for i in range(8))==expected_token
  assert logic(after,7)==int(bit==0)
  steps.append(dict(bit=bit,pre_evaluation_residue_v=residual,keep=bool(keep),agrees_with_pre_evaluation_residue=analog_correct,code_after_update=expected,trial_logic_settled_after_update_ns=settled_after_ns))
  trial=expected
 final=win(114,114.8) if args.fast else win(265,270);assert code(final)==c['final_code']==trial and logic(final,7)==1
 c['verified_steps']=steps
 c['ideal_capacitor_quantizer_code']=int(np.clip(np.floor(128-c['input_difference_v']/(2/256)),0,255))
 c['difference_from_ideal_capacitor_quantizer_codes']=c['final_code']-c['ideal_capacitor_quantizer_code']
 c['final_residue_v']=float(np.mean(final[:,1]-final[:,2]))
r['decision_capture_and_token_advancement_checked']=True;r['all_comparator_decisions_agree_with_residue']=all(step['agrees_with_pre_evaluation_residue'] for c in r['cases'] for step in c['verified_steps']);r['target_throughput_met']=False;r['adc_precision_established']=False
(P/('evidence/adc-sar8-'+tag+'-screen.json')).write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps([{k:v for k,v in c.items() if k not in ('artifacts_sha256','verified_steps')} for c in r['cases']],indent=2))
