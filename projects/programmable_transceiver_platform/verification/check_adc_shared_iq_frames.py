#!/usr/bin/env python3
"""Completion, both-channel capture, and shared-reference decision windows."""
import hashlib,json,re,sys
edge="early" if "--edge-early" in sys.argv else "late" if "--edge-late" in sys.argv else None
two_k="--two-k" in sys.argv or edge is not None
damping="--damping" in sys.argv or two_k
fixed_references="--fixed-references" in sys.argv
compensation="--compensation" in sys.argv
early_input="--early-input" in sys.argv
receiver_cm="--receiver-cm" in sys.argv or early_input or compensation or fixed_references or damping
same_history="--same-history" in sys.argv or receiver_cm
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/('scratch/transceiver-adc-shared-iq-same' if same_history else 'scratch/transceiver-adc-shared-iq-frames');B=R/('scratch/transceiver-adc-shared-iq-frames' if same_history else 'scratch/transceiver-adc-shared-iq-preflight')
if receiver_cm:W=R/'scratch/transceiver-adc-shared-iq-receiver-cm';B=R/'scratch/transceiver-adc-shared-iq-same'
if early_input:W=R/'scratch/transceiver-adc-shared-iq-early-input';B=R/'scratch/transceiver-adc-shared-iq-receiver-cm'
if compensation:W=R/'scratch/transceiver-adc-shared-iq-compensation';B=R/'scratch/transceiver-adc-shared-iq-receiver-cm'
if fixed_references:W=R/'scratch/transceiver-adc-shared-iq-fixed-references';B=R/'scratch/transceiver-adc-shared-iq-receiver-cm'
if damping:W=R/'scratch/transceiver-adc-shared-iq-damping';B=R/'scratch/transceiver-adc-shared-iq-receiver-cm'
if two_k:W=R/'scratch/transceiver-adc-shared-iq-damping2k'
if edge:W=R/('scratch/transceiver-adc-shared-iq-edge-'+edge);B=R/'scratch/transceiver-adc-shared-iq-damping2k'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());src=B/('frames.spice' if same_history else 'preflight.spice');assert sha(src)==m['baseline_deck_sha256'];d=(W/'frames.spice').read_text();assert sha(W/'frames.spice')==m['deck_sha256_before']
if edge:
 old_lines=src.read_text().splitlines();new_lines=d.splitlines();assert len(old_lines)==len(new_lines)
 changed=0
 for old,new in zip(old_lines,new_lines):
  if old==new:continue
  assert old.startswith(('VS ','VSB ')) and new.split()[:3]==old.split()[:3]
  before_tokens=re.findall(r'([0-9.]+)n',old);after_tokens=re.findall(r'([0-9.]+)n',new)
  assert len(before_tokens)==len(after_tokens)
  delta=-.1 if edge=='early' else .1
  for a,b in zip(before_tokens,after_tokens):
   expected_delta=delta if float(a) in [70,70.1,120,120.1,170,170.1] else 0
   assert abs(float(b)-float(a)-expected_delta)<1e-10
  assert re.sub(r'[0-9.]+n','TIME',old)==re.sub(r'[0-9.]+n','TIME',new)
  changed+=1
 assert changed==2
elif receiver_cm:
 expected=src.read_text();changes={}
 for line in expected.splitlines():
  if line.split(' ')[0] in ('VIP','VIN','VQ_IP','VQ_IN'):changes[line]=(line.replace('60n ','50n ').replace('60.1n ','50.1n ') if early_input else line.replace('1.85','1.27').replace('1.45','0.87'))
 if compensation:changes={line:line.replace('CC=.5p','CC=1p') for line in expected.splitlines() if 'pt_sample_driver_headroom CC=.5p' in line}
 if fixed_references:
  old='XREF HR LR VH VL RBN RBP VREFSUP 0 pt_adc_reference_pair_tuned'
  changes={old:'XREF HR LR VHISO VLISO RBN RBP VREFSUP 0 pt_adc_reference_pair_tuned\nVFIXH VH 0 2.15\nVFIXL VL 0 1.15'}
 if damping:
  cell=(P/'analog/adc/sample_driver_headroom.spice').read_text()
  assert cell.count('RC X Z 100')==1
  changes={'.include /screen/adc/sample_driver_headroom.spice':cell.replace('RC X Z 100','RC X Z 2k' if two_k else 'RC X Z 1k')}
 assert len(changes)==(1 if fixed_references or damping else 4) and changes==m['changes']
 for old,new in changes.items():expected=expected.replace(old,new)
 assert d==expected
elif same_history:
 assert m['same_history'] is True
 expected=src.read_text();lines=expected.splitlines()
 for primary,secondary,node in [('VIP','VQ_IP','Q_SP'),('VIN','VQ_IN','Q_SN')]:
  first=next(l for l in lines if l.startswith(primary+' '));old=next(l for l in lines if l.startswith(secondary+' '));new=secondary+' '+node+' 0 '+first.split(' ',3)[3]
  assert expected.count(old)==1;expected=expected.replace(old,new)
 assert d==expected
else:assert d.replace('tran 5p 209.9n 0 5p','tran 5p 1n 0 5p').replace('/work/frames.dat','/work/preflight.dat')==src.read_text()
out=dict(status='pending',completed=False,input_relationship='same' if same_history else 'opposite',frames=[])
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 for ext,h in r['artifacts_sha256'].items():assert sha(W/('frames'+ext))==h
 log=(W/'frames.log').read_text().lower();fail=re.search(r'timestep too small; time = ([0-9.e+-]+)',log);out.update(status='terminal',provenance=r,failure_time_s=float(fail.group(1)) if fail else None)
 if (W/'frames.dat').exists():
  with (W/'frames.dat').open() as f:h=f.readline().lower().split()
  assert h==['time']+next(l for l in d.splitlines() if l.startswith('wrdata ')).lower().split()[2:]
  a=np.loadtxt(W/'frames.dat',skiprows=1);assert a.ndim==2 and a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>=0)
  out.update(actual_stop_ns=float(a[-1,0]*1e9),repeated_printed_time_intervals=int(np.sum(np.diff(a[:,0])==0)),completed=bool(r['returncode']==0 and not r['timed_out'] and 'aborted' not in log and a[-1,0]+1e-21>=209.9e-9))
  if fixed_references:
   clamp_errors={node:float(np.max(abs(a[:,h.index('v('+node+')')]-target))) for node,target in [('vh',2.15),('vl',1.15)]}
   assert max(clamp_errors.values())<1e-9
   out['ideal_reference_clamp_max_error_v']=clamp_errors
  for hold in (70,120,170):
   if a[-1,0]<(hold+39.7)*1e-9:continue
   capture=a[(a[:,0]>=(hold+39.3)*1e-9)&(a[:,0]<=(hold+39.7)*1e-9)];assert len(capture)>1
   first=a[(a[:,0]>=(hold+.2)*1e-9)&(a[:,0]<=(hold+.35)*1e-9)];assert len(first)>1
   channels={}
   for label,prefix in [('I',''),('Q','q_')]:
    bits=capture[:,[h.index(f'v({prefix}d{i})') for i in range(8)]];codes=(bits>1.65).astype(int)@2**np.arange(8)
    channels[label]=dict(captured_codes=np.unique(codes).tolist(),all_samples_at_logic_rails=bool(np.all((bits<.33)|(bits>2.97))),capture_time_top_plate_differential_mean_v=float(np.mean(capture[:,h.index(f'v({prefix}hp)')]-capture[:,h.index(f'v({prefix}hn)')])))
    initial_diff=first[:,h.index(f'v({prefix}hp)')]-first[:,h.index(f'v({prefix}hn)')]
    channels[label]['first_predecision_plate_differential_range_v']=[float(initial_diff.min()),float(initial_diff.max())]
    channels[label]['first_predecision_window_ns']=[hold+.2,hold+.35]
    initial_cm=(first[:,h.index(f'v({prefix}hp)')]+first[:,h.index(f'v({prefix}hn)')])/2
    channels[label]['first_predecision_plate_common_mode_range_v']=[float(initial_cm.min()),float(initial_cm.max())]

   steps=[]
   for bit in range(7,-1,-1):
    lo=hold+.2+5*(7-bit);hi=hold+.35+5*(7-bit);w=a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)];assert len(w)>1;vh=w[:,h.index('v(vh)')];vl=w[:,h.index('v(vl)')]
    steps.append(dict(bit=bit,window_ns=[lo,hi],span_sample_mean_v=float(np.mean(vh-vl)),span_motion_v=float(np.ptp(vh-vl)),high_max_error_v=float(abs(vh-2.15).max()),low_max_error_v=float(abs(vl-1.15).max())))
   for step in steps:
    lo,hi=step['window_ns'];w=a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)]
    step['comparator_input_common_mode_range_v']={}
    for label,prefix in [('I',''),('Q','q_')]:
     cm=(w[:,h.index(f'v({prefix}hp)')]+w[:,h.index(f'v({prefix}hn)')])/2
     step['comparator_input_common_mode_range_v'][label]=[float(cm.min()),float(cm.max())]
   active=a[(a[:,0]>=hold*1e-9)&(a[:,0]<=(hold+39.7)*1e-9)];t=active[:,0]
   observed_power={key:float(-3.3*np.trapezoid(active[:,h.index(key)],t)/(t[-1]-t[0])) for key in ['i(vlog)','i(vdrv)','i(vbuf)','i(vrefsup)']}
   out['frames'].append(dict(hold_ns=hold,channels=channels,shared_reference_decisions=steps,observed_aggregate_supply_power_w=observed_power))
out['limitations']=['Selected input relationship with simultaneous ideal phases; not a bound for arbitrary I/Q switching or timing skew.', 'Captured code/rail checks do not establish accuracy, ENOB, noise or modem performance.', 'Single actual reference pair and reservoir; ideal targets, supply and bias remain.', 'Decision sample means match prior diagnostic convention, not time-weighted aperture estimates.', 'Capture-time top-plate state follows the CDAC track-mask reset; it is not a held-sample accuracy measurement.', 'Reported supply powers aggregate both channels on ideal rails and exclude unsaved VDD comparator/sampler supply; not complete ADC/chip power.']
if fixed_references:
 out['limitations']=[x for x in out['limitations'] if not x.startswith('Single actual reference pair')]
 out['limitations'].append('Ideal reference clamps replace loaded physical reference outputs; not implementable regulation or power evidence. Reference amplifiers remain unloaded for observation continuity.')
(P/('evidence/adc-shared-iq-edge-'+edge+'.json' if edge else 'evidence/adc-shared-iq-damping2k.json' if two_k else 'evidence/adc-shared-iq-damping.json' if damping else 'evidence/adc-shared-iq-fixed-references.json' if fixed_references else 'evidence/adc-shared-iq-compensation.json' if compensation else 'evidence/adc-shared-iq-early-input.json' if early_input else 'evidence/adc-shared-iq-receiver-cm.json' if receiver_cm else 'evidence/adc-shared-iq-same.json' if same_history else 'evidence/adc-shared-iq-frames.json')).write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'],len(out['frames']))
