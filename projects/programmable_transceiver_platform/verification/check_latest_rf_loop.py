#!/usr/bin/env python3
"""Latest connected RX loop diagnostics; completion is not a lock criterion."""
import argparse,hashlib,json
ap=argparse.ArgumentParser();ap.add_argument("--extended",action="store_true");ap.add_argument("--selective",action="store_true");args=ap.parse_args();assert not (args.extended and args.selective)
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-latest-rf-loop';B=R/'scratch/transceiver-latest-rf-loop-prepared'
if args.extended:W=R/'scratch/transceiver-latest-rf-loop-extended';B=R/'scratch/transceiver-latest-rf-loop-extended-prepared'
if args.selective:W=R/'scratch/transceiver-latest-rf-loop-selective';B=R/'scratch/transceiver-latest-rf-loop-selective-prepared'
horizon_ns=8001 if (args.extended or args.selective) else 3201
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
m=json.loads((W/'manifest.json').read_text());d=(W/'latest.spice').read_text();assert d==(B/'latest.spice').read_text() and sha(W/'latest.spice')==m['deck_sha256' if args.selective else 'deck_sha256_before']
assert 'VCTRL ' not in d and 'VCLAMP ' not in d and 'XD1 P N ' in d
out=dict(status='pending',completed=False,limitations=['Seeded zero-RF test, ideal biases/supplies and absent ADC/interface loads.','No cold startup, noise, modulation or lock qualification.'])
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before'] and (args.selective or r['deck_unchanged']);out['provenance']=r
 for e,h in r['artifacts_sha256'].items():assert sha(W/('latest'+e))==h
 out['status']='terminal_without_waveform'
 if (W/'latest.dat').exists():
  with (W/'latest.dat').open() as f:header=f.readline().lower().split()
  expected=['time']+d.split('wrdata /work/latest.dat ')[1].split('\n')[0].lower().split();assert header==expected
  a=np.loadtxt(W/'latest.dat',skiprows=1);assert a.shape[1]==len(header) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
  t=a[:,0];out['actual_stop_ns']=float(t[-1]*1e9);out['completed']=bool(r['returncode']==0 and not r['timed_out'] and t[-1]+1e-21>=horizon_ns*1e-9 and 'aborted' not in (W/'latest.log').read_text().lower());out['status']='completed_seeded_diagnostic' if out['completed'] else 'incomplete_transient'
  def v(n):return a[:,header.index(n)]
  def edges(y):
   k=np.flatnonzero((y[:-1]<1.65)&(y[1:]>=1.65));return t[k]+(1.65-y[k])*np.diff(t)[k]/np.diff(y)[k]
  ref=edges(v('v(ref)'));fb=edges(v('v(fb)'));ref=ref[ref>=100e-9];fb=fb[fb>=100e-9];n=min(len(ref),len(fb))
  out['phase']=dict(reference_edges=len(ref),feedback_edges=len(fb),reference_times_ns=(ref[:n]*1e9).tolist(),ordinal_feedback_minus_reference_ns=((fb[:n]-ref[:n])*1e9).tolist())
  out['node_ranges_v']={name:[float(v(name).min()),float(v(name).max())] for name in ('v(ctrl)','v(dummy)','v(lg)','v(ls)','v(fip)','v(fin)','v(fqp)','v(fqn)')}
  out['windows']=[]
  for lo,hi in ((100,200),(500,600),(1100,1200),(2000,2100),(3000,3100),(5000,5100),(7000,7100),(7900,8000)):
   if t[-1]+1e-21<hi*1e-9:continue
   mask=(t>=lo*1e-9)&(t<=hi*1e-9);wt=t[mask];y=(v('v(p)')-v('v(n)'))[mask]
   k=np.flatnonzero((y[:-1]<0)&(y[1:]>=0));e=wt[k]-y[k]*np.diff(wt)[k]/np.diff(y)[k]
   def span(y):return [float(y[mask].min()),float(y[mask].max())]
   window=dict(window_ns=[lo,hi],vco_frequency_hz=float((len(e)-1)/(e[-1]-e[0])) if len(e)>2 else None,control_range_v=span(v('v(ctrl)')),dummy_range_v=span(v('v(dummy)')),pump_charge_fc=float(np.trapezoid(v('i(vsense)')[mask],wt)*1e15),filter_output={})
   for label,pos,neg in (('i','v(fip)','v(fin)'),('q','v(fqp)','v(fqn)')):
    window['filter_output'][label]=dict(common_mode_range_v=span((v(pos)+v(neg))/2),differential_range_v=span(v(pos)-v(neg)))
   out['windows'].append(window)
  if n>=21:
   rt=ref[:n][-21:];ft=fb[:n][-21:];phase=ft-rt;x=rt-rt[0];slope,intercept=np.polyfit(x,phase,1)
   out['late_phase_diagnostic']=dict(window_ns=[float(rt[0]*1e9),float(rt[-1]*1e9)],phase_drift_ns=float((phase[-1]-phase[0])*1e9),phase_slope_s_per_s=float(slope),detrended_peak_to_peak_ps=float(np.ptp(phase-(slope*x+intercept))*1e12),limitations='Ordinal pairing with startup-dependent alignment; deterministic residual is not intrinsic jitter. No lock threshold asserted.')
  mask=t>=100e-9
  if np.count_nonzero(mask)>1:
   out['post100ns_supply_power_w']={name:float(-3.3*np.trapezoid(v(name)[mask],t[mask])/(t[mask][-1]-t[mask][0])) for name in ('i(vpll)','i(vbuf)','i(vlna)','i(vbb)','i(vdiv)','i(vdrv)')}
(P/('evidence/latest-rf-loop-selective.json' if args.selective else 'evidence/latest-rf-loop-extended.json' if args.extended else 'evidence/latest-rf-loop.json')).write_text(json.dumps(out,indent=2)+'\n');print(out['status'],out['completed'])
