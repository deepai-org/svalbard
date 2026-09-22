#!/usr/bin/env python3
"""Candidate tradeoffs on native timelines; no automatic promotion."""
import argparse,hashlib,json
ap=argparse.ArgumentParser();ap.add_argument("--reference-mirror",action="store_true");ap.add_argument("--reference-hybrid",action="store_true");ap.add_argument("--reference-output2",action="store_true");args=ap.parse_args();assert sum((args.reference_mirror,args.reference_hybrid,args.reference_output2))<=1
if args.reference_output2:args.reference_hybrid=True
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';experiment_name='reference-hybrid-output2-frames' if args.reference_output2 else 'reference-hybrid-frames' if args.reference_hybrid else 'reference-long-mirror-frames' if args.reference_mirror else 'bit6-complement';W=R/'scratch'/('transceiver-'+experiment_name);B=R/'scratch/transceiver-cdac-probe-reltol/probed'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());assert sha(W/'frames.spice')==m['deck_sha256_before'] and sha(B/'frames.spice')==m['parent_deck_sha256']
s=(W/'frames.spice').read_text().replace('/work/frames.dat','/work/probed/frames.dat')
if args.reference_mirror or args.reference_hybrid:
 pair=(P/'analog/reference/adc_reference_pair_tuned.spice').read_text()
 for file in ('buffer_scaled_tune.spice','buffer_complement_tune.spice'):
  cell=(P/'analog/reference'/file).read_text()
  if args.reference_hybrid:
   if file=='buffer_complement_tune.spice':
    ncell=(P/'analog/reference/buffer_scaled_tune.spice').read_text()
    for instance in ('XIP','XIN','XT','XMP','XMN'):
     old=next(l for l in cell.splitlines() if l.startswith(instance+' '))
     new=next(l for l in ncell.splitlines() if l.startswith(instance+' '))
     cell=cell.replace(old,new)
  else:
   for line in cell.splitlines():
    if line.startswith(('XMP ','XMN ')):cell=cell.replace(line,line.replace('w=8u l=.5u','w=16u l=1u'))
  if args.reference_output2 and file=='buffer_complement_tune.spice':
   old='XOUT OUT X VDD VDD pfet_03v3 w=8u l=.5u m={8*S}'
   assert cell.count(old)==1
   cell=cell.replace(old,old.replace('m={8*S}','m={16*S}'))
  pair=pair.replace('.include /screen/reference/'+file,cell)
 assert pair==m['added_subcircuit']
 assert s.replace(pair,'.include /screen/reference/adc_reference_pair_tuned.spice')==(B/'frames.spice').read_text()
else:
 for old,new in m['changes']:assert s.count(new)==1;s=s.replace(new,old)
 a='.include /screen/adc/code_driver_small.spice';assert s.replace(a+'\n'+m['added_subcircuit'],a)==(B/'frames.spice').read_text()
out=dict(status='pending',completed=False,manifest_sha256=sha(W/'manifest.json'),cases={})
if (W/'result.json').exists():
 for name,root in [('baseline',B),('candidate',W)]:
  r=json.loads((root/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']
  for ext,h in r['artifacts_sha256'].items():assert sha(root/('frames'+ext))==h
  log=(root/'frames.log').read_text();errors=[l.strip() for l in log.splitlines() if any(x in l.lower() for x in ['error','aborted','warning'])]
  result=dict(returncode=r['returncode'],timed_out=r['timed_out'],errors=errors,artifacts_sha256=r['artifacts_sha256'],completed=False)
  out['cases'][name]=result
  if r['returncode']!=0 or r['timed_out'] or errors:continue
  with (root/'frames.dat').open() as f:h=f.readline().lower().split()
  data=np.loadtxt(root/'frames.dat',skiprows=1);t=data[:,0]
  expected=next(l for l in (root/'frames.spice').read_text().splitlines() if l.startswith('wrdata ')).lower().split()[2:]
  assert h==['time']+expected and data.shape[1]==len(h) and np.isfinite(data).all() and np.all(np.diff(t)>0)
  result['actual_stop_s']=float(t[-1])
  if t[-1]+1e-21<209.9e-9:continue
  result['completed']=True
  def v(n):return data[:,h.index(n)]
  def interval(y,lo,hi):
   lo*=1e-9;hi*=1e-9;assert t[0]<=lo<hi<=t[-1]+1e-21;tt=np.r_[lo,t[(t>lo)&(t<hi)],hi];return tt,np.interp(tt,t,y)
  def integral(y,lo,hi):
   tt,yy=interval(y,lo,hi);return float(np.trapezoid(yy,tt))
  decisions=[];held=[];captures=[];spans=[]
  for hold in (70,120,170):
   for bit in range(8):
    tt,span=interval(v('v(vh)')-v('v(vl)'),hold+5*bit+.2,hold+5*bit+.35)
    spans.append(dict(hold_ns=hold,bit_index=bit,min_v=float(span.min()),max_v=float(span.max()),motion_v=float(np.ptp(span)),max_nominal_span_error_v=float(abs(span-1).max())))
    for rail,target in [('h',2.15),('l',1.15)]:
     tt,y=interval(v(f'v(v{rail})'),hold+5*bit+.2,hold+5*bit+.35)
     decisions.append(dict(hold_ns=hold,bit_index=bit,rail=rail,max_error_v=float(abs(y-target).max()),motion_v=float(np.ptp(y))))
   for prefix in ('','q_'):
    held.append(dict(hold_ns=hold,channel=prefix or 'i',diff_v=integral(v(f'v({prefix}hp)')-v(f'v({prefix}hn)'),hold+.2,hold+.35)/.15e-9))
    mask=(t>=(hold+39.3)*1e-9)&(t<=(hold+39.7)*1e-9);assert mask.any()
    bits=data[mask][:,[h.index(f'v({prefix}d{i})') for i in range(8)]]
    assert np.all((bits<.33)|(bits>2.97))
    captures.append(dict(hold_ns=hold,channel=prefix or 'i',codes=np.unique((bits>1.65).astype(int)@2**np.arange(8)).tolist()))
  currents=[]
  for rail in ('h','l'):
   y=v(f'i(vref{rail}_del)')-v(f'i(vref{rail}_res)')
   for lo,hi in [(60,109.9),(110,159.9),(160,209.9),(122.5,125.35)]:
    tt,yy=interval(y,lo,hi);k=int(abs(yy).argmax())
    currents.append(dict(rail=rail,window_ns=[lo,hi],peak_signed_a=float(yy[k]),signed_charge_c=float(np.trapezoid(yy,tt))))
  crossings={}
  for n in ('v(b6)','v(b6b)','v(q_b6)','v(q_b6b)'):
   y=v(n);ix=np.flatnonzero((y[:-1]-1.65)*(y[1:]-1.65)<0)
   crossings[n]=[dict(time_ns=float((t[k]+(1.65-y[k])*(t[k+1]-t[k])/(y[k+1]-y[k]))*1e9),direction='rising' if y[k+1]>y[k] else 'falling') for k in ix]
  result.update(reference_span_windows=spans,decisions=decisions,held=held,captures=captures,currents=currents,gate_midpoint_crossings=crossings,reference_energy_j=-3.3*integral(v('i(vrefsup)'),60,209.9),driver_energy_j=-3.3*integral(v('i(vdrv)'),60,209.9))
 out['completed']=all(x['completed'] for x in out['cases'].values());out['status']='terminal'
 if out['completed']:
  b=out['cases']['baseline'];c=out['cases']['candidate']
  out['comparison']=dict(codes_match=b['captures']==c['captures'],reference_energy_change_j=c['reference_energy_j']-b['reference_energy_j'],driver_energy_change_j=c['driver_energy_j']-b['driver_energy_j'],held_change_v=[y['diff_v']-x['diff_v'] for x,y in zip(b['held'],c['held'])],reference_error_change_v=[y['max_error_v']-x['max_error_v'] for x,y in zip(b['decisions'],c['decisions'])])
out['limitations']=['No automatic candidate promotion; compare improvements and regressions together.','Driver energy covers VDRV only, not whole ADC/chip power.','1.65V crossings are logic timing markers, not channel thresholds.','Terminal current includes displacement; no proof of overlap or numerical convergence.']
(P/'evidence'/(experiment_name+'.json')).write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'])
