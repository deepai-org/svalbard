#!/usr/bin/env python3
"""Locate common-mode-dependent sample error using saved driver/plate vectors."""
import argparse,hashlib,json
ap=argparse.ArgumentParser();variants=ap.add_mutually_exclusive_group();variants.add_argument("--early-input",action="store_true");variants.add_argument("--compensation",action="store_true");variants.add_argument("--fixed-references",action="store_true");variants.add_argument("--damping",action="store_true");variants.add_argument("--two-k",action="store_true");args=ap.parse_args()
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';rows=[];hashes={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
DC=R/'scratch/transceiver-adc-receiver-cm';dr=json.loads((DC/'result.json').read_text());dc_case=next(c for c in dr['cases'] if c['load_ua']==0)
for ext,h in dc_case['artifacts_sha256'].items():assert sha(DC/('load0'+ext))==h
with (DC/'load0.dat').open() as f:dh=f.readline().lower().split()
da=np.loadtxt(DC/'load0.dat',skiprows=1);hashes['unloaded_dc']=dc_case['artifacts_sha256']
cases=['same','receiver-cm']
if args.early_input:cases.append('early-input')
if args.compensation:cases.append('compensation')
if args.fixed_references:cases.append('fixed-references')
if args.damping:cases.append('damping')
if args.two_k:cases.extend(['damping','damping2k'])
for name in cases:
 W=R/('scratch/transceiver-adc-shared-iq-'+name);r=json.loads((W/'result.json').read_text());assert r['returncode']==0 and not r['timed_out']
 for ext,h in r['artifacts_sha256'].items():assert sha(W/('frames'+ext))==h
 hashes[name]=r['artifacts_sha256']
 with (W/'frames.dat').open() as f:h=f.readline().lower().split()
 a=np.loadtxt(W/'frames.dat',skiprows=1);assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>=0) and a[-1,0]+1e-21>=209.9e-9
 for hold in (70,120,170):
  windows={}
  for label,lo,hi in (('tracking',hold-.3,hold-.15),('held_predecision',hold+.2,hold+.35)):
   w=a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)];t=w[:,0];assert len(w)>2 and t[-1]>t[0]
   def v(n):return w[:,h.index(n)]
   def mean(y):return float(np.trapezoid(y,t)/(t[-1]-t[0]))
   windows[label]=dict(window_ns=[lo,hi],driver_differential_v=mean(v('v(ip)')-v('v(in)')),plate_differential_v=mean(v('v(hp)')-v('v(hn)')),plate_minus_driver_differential_v=mean(v('v(hp)')-v('v(hn)')-v('v(ip)')+v('v(in)')),plate_common_mode_v=mean((v('v(hp)')+v('v(hn)'))/2),reference_span_v=mean(v('v(vh)')-v('v(vl)')))
  targets=(1.45,1.85) if name=='same' else (.87,1.27)
  if hold==120:targets=targets[::-1]
  w=a[(a[:,0]>=(hold-.3)*1e-9)&(a[:,0]<=(hold-.15)*1e-9)];t=w[:,0];legs={}
  for label,node,target in zip(('p','n'),('v(ip)','v(in)'),targets):
   measured=float(np.trapezoid(w[:,h.index(node)],t)/(t[-1]-t[0]));k=int(np.argmin(abs(da[:,0]-target)));assert abs(da[k,0]-target)<1e-12
   dc=float(da[k,dh.index('v(out)')]);legs[label]=dict(source_target_v=target,unloaded_dc_output_v=dc,tracking_driver_mean_v=measured,tracking_minus_unloaded_dc_v=measured-dc)
  windows['tracking']['driver_legs_vs_unloaded_dc']=legs
  rows.append(dict(case=name,hold_ns=hold,windows=windows,plate_differential_change_at_hold_v=windows['held_predecision']['plate_differential_v']-windows['tracking']['plate_differential_v']))
out=dict(status='saved_waveform_sampling_diagnostic',cases=rows,artifacts_sha256=hashes,limitations=['Only I driver outputs were saved; Q held plates/codes are separate evidence.','Before/after change combines switch feedthrough, settling and other simultaneous circuit activity; does not isolate a transistor mechanism.','Means use actual elapsed time; repeated printed timestamps contribute zero interval, no interpolation across them.','Ideal source drive persists; not actual RF-filter-loaded performance.'])
suffix='-damping2k' if args.two_k else '-damping' if args.damping else '-fixed-references' if args.fixed_references else '-early' if args.early_input else '-compensation' if args.compensation else ''
(P/('evidence/adc-cm-sampling'+suffix+'.json')).write_text(json.dumps(out,indent=2)+'\n')
for x in rows:print(x['case'],x['hold_ns'],x['windows']['tracking']['driver_differential_v'],x['windows']['tracking']['plate_differential_v'],x['windows']['held_predecision']['plate_differential_v'],x['plate_differential_change_at_hold_v'])
