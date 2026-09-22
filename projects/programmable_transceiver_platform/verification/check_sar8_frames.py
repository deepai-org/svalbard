#!/usr/bin/env python3
"""Check each frame and preserve analog decision errors instead of hiding them."""
import argparse,hashlib,json,re
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];P=ROOT/'projects/programmable_transceiver_platform';B=ROOT/'scratch/transceiver-adc-sar8-driven'
parser=argparse.ArgumentParser();parser.add_argument('--masked',action='store_true');parser.add_argument('--early',action='store_true');parser.add_argument('--strong',action='store_true');args=parser.parse_args();args.early=args.early or args.strong;args.masked=args.masked or args.early;tag='sar8-strong-mask-frames' if args.strong else ('sar8-early-mask-frames' if args.early else ('sar8-masked-frames' if args.masked else 'sar8-frames'));W=ROOT/('scratch/transceiver-adc-'+tag)
r=json.loads((W/'result.json').read_text())
for path,digest in r['source_sha256'].items():
 actual=P/'analog'/path.removeprefix('/screen/') if path.startswith('/screen/') else ROOT/'ip/blocks/analog/wifi_80211b'/path.removeprefix('/wifi/')
 assert hashlib.sha256(actual.read_bytes()).hexdigest()==digest
assert len(r['cases'])==2
for c in r['cases']:
 name=c['name'];base=(B/f"vin{c['input_differences_v'][0]:g}_change0.spice").read_text()
 assert hashlib.sha256(base.encode()).hexdigest()==c['baseline_deck_sha256']
 for suffix,digest in c['artifacts_sha256'].items():assert hashlib.sha256((W/(name+suffix)).read_bytes()).hexdigest()==digest
 d=(W/(name+'.spice')).read_text()
 if args.strong:
  original=(ROOT/'scratch/transceiver-adc-sar8-early-mask-frames'/(name+'.spice')).read_text()
  d=d.replace('sar_track_mask_strong.spice','sar_track_mask.spice').replace('pt_sar_track_mask_strong','pt_sar_track_mask')
  assert d==original
 def fixture(prefix,times_ns):
  line=next(line for line in d.splitlines() if line.startswith(prefix))
  tokens=re.search(r'PWL\((.+)\)',line).group(1).split()
  times=np.array([float(x.removesuffix('n')) for x in tokens[::2]])
  values=np.array([float(x) for x in tokens[1::2]])
  return np.interp(times_ns,times,values)
 for frame,(hold,vin) in enumerate(zip(c['hold_times_ns'],c['input_differences_v'])):
  assert np.allclose(fixture('VIP SP 0 ',[hold-.5,hold+39])-fixture('VIN SN 0 ',[hold-.5,hold+39]),vin)
  assert np.allclose(fixture('VS SC 0 ',[hold-2,hold-.2]),3.3)
  assert np.allclose(fixture('VS SC 0 ',[hold+.2,hold+39.7]),0)
  assert np.allclose(fixture('VSB SCB 0 ',[hold+.2,hold+39.7]),3.3)
  if frame:assert np.allclose(fixture('VRST RN 0 ',[hold-9.8,hold-9.2]),0)
  if args.early:
   assert np.allclose(fixture('VMASK MASKB 0 ',[hold+.2,hold+37.7]),3.3)
   assert np.allclose(fixture('VMASK MASKB 0 ',[hold+38,hold+39.7]),0)
   if frame:assert np.allclose(fixture('VMASK MASKB 0 ',[hold-10.2]),0)
 if args.masked:
  extra='.include /screen/adc/sar_track_mask.spice\nXTRACK '+' '.join(f'D{i}' for i in range(8))+' SCB '+' '.join(f'SD{i}' for i in range(8))+' VLOG 0 pt_sar_track_mask\n'
  if args.early:
   extra=extra.replace(' SCB ',' MASKB ')
   d=re.sub(r'^VMASK MASKB 0 .+\n','',d,flags=re.M)
  assert extra in d;d=d.replace(extra,'')
  for i in range(8):d=d.replace(f'XDRV{i} SD{i} ',f'XDRV{i} D{i} ')
  d=d.replace(' '+' '.join(f'v(SD{i})' for i in range(8)),'')
  original=(ROOT/'scratch/transceiver-adc-sar8-frames'/(name+'.spice')).read_text();assert d==original
 # Circuit must be unchanged after reversing any explicit mask insertion.
 for prefix in ('VRST RN 0 ','VSTART START 0 ','VUPDATE UPDATE 0 ','VS SC 0 ','VSB SCB 0 ','VC CLK 0 ','VIP SP 0 ','VIN SN 0 ','tran '):
  original=next(line for line in base.splitlines() if line.startswith(prefix));d=re.sub('^'+re.escape(prefix)+'.+$',original,d,flags=re.M)
 d=d.replace(f'/work/{name}.dat',f"/work/vin{c['input_differences_v'][0]:g}_change0.dat");assert d==base
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape[1]==(39 if args.masked else 31) and np.isfinite(a).all() and a[-1,0]>=209.9e-9
 def win(lo,hi):return a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)]
 def logic(w,col):
  high=bool(w[:,col].min()>2.97);low=bool(w[:,col].max()<.33);assert high or low,f'{name}: unsettled logic column {col}';return int(high)
 def code(w):return sum(logic(w,8+i)*2**i for i in range(8))
 frames=[]
 for hold,vin in zip(c['hold_times_ns'],c['input_differences_v']):
  pretrack_valid=None
  initial=win(hold-.5,hold-.2);assert code(initial)==128
  assert sum(logic(initial,16+i)*2**i for i in range(8))==128 and logic(initial,7)==0
  if args.masked:
   masked=win(hold-4,hold-.2)
   assert sum(logic(masked,31+i)*2**i for i in range(8))==128
   if args.early and hold>70:
    before_track=win(hold-10.2,hold-10.05)
    pretrack_valid=bool(np.all(before_track[:,31:38]<.33) and np.all(before_track[:,38]>2.97))
  trial=128;steps=[]
  for bit in range(7,-1,-1):
   edge=hold+2.5+5*(7-bit);before=win(edge-.5,edge-.2)
   # Last result must be checked before next-frame reset at hold+40ns.
   after=win(edge+1.8,edge+2.2) if bit==0 else win(edge+2.5,edge+2.8)
   assert code(before)==trial
   if args.masked:assert sum(logic(before,31+i)*2**i for i in range(8))==trial
   keep=logic(before,27);assert logic(before,26)==1-keep
   pre=win(edge-2.3,edge-2.15);residue=float(np.mean(pre[:,1]-pre[:,2]))
   retained=trial if keep else trial&~(1<<bit);expected=retained|(1<<(bit-1)) if bit else retained
   assert code(after)==expected
   assert sum(logic(after,16+i)*2**i for i in range(8))==(1<<(bit-1) if bit else 0)
   assert logic(after,7)==int(bit==0)
   steps.append(dict(bit=bit,pre_evaluation_residue_v=residue,keep=bool(keep),agrees_with_residue=keep==int(residue<0),code_after_update=expected));trial=expected
  final=win(hold+39.3,hold+39.7);assert code(final)==trial and logic(final,7)==1
  residue_window=win(hold+37,hold+37.3) if args.early else final
  frames.append(dict(hold_ns=hold,input_difference_v=vin,pretrack_midcode_rails_valid=pretrack_valid,final_code=trial,reported_residue_window_ns=([hold+37,hold+37.3] if args.early else [hold+39.3,hold+39.7]),final_residue_v=float(np.mean(residue_window[:,1]-residue_window[:,2])),ideal_capacitor_quantizer_code=int(np.clip(np.floor(128-vin/(2/256)),0,255)),steps=steps))
  if args.early:frames[-1]['last_trial_residue_v']=frames[-1].pop('final_residue_v')
 c['frames']=frames
r['frame_logic_and_decision_capture_checked']=True;r['all_comparator_decisions_agree_with_residue']=all(s['agrees_with_residue'] for c in r['cases'] for f in c['frames'] for s in f['steps']);r['qualified_20msps_adc']=False;r['reported_residue_is_last_trial_before_update']=bool(args.early);r['pretrack_deadline_pass']=all(f['pretrack_midcode_rails_valid'] is not False for c in r['cases'] for f in c['frames']) if args.early else None
if args.early and not r['pretrack_deadline_pass']:r['status']='early_mask_output_logic_rail_deadline_failed'
r['pretrack_observation_scope']='SD0..SD7 mask outputs upstream of code buffers; final switch-gate and capacitor-plate settling are not directly measured by this check.'
(P/('evidence/adc-'+tag+'-screen.json')).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps([dict(name=c['name'],frames=[{k:v for k,v in f.items() if k!='steps'} for f in c['frames']]) for c in r['cases']],indent=2))

if args.early:assert r['pretrack_deadline_pass'],'Pretrack mask-output rail criterion failed; downstream switch-gate settling unmeasured; failed evidence retained'
