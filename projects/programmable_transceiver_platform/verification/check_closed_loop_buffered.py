#!/usr/bin/env python3
"""Audit buffered actual-feedback experiment without equating settling with lock."""
import argparse,hashlib,json,re
ap=argparse.ArgumentParser();ap.add_argument("--follower",action="store_true");ap.add_argument("--pwl",action="store_true");args=ap.parse_args()
if args.pwl:args.follower=True
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-closed-loop-buffered';B=R/'scratch/transceiver-closed-loop-gear/closed.spice'
if args.follower:
 W=R/'scratch/transceiver-closed-loop-follower';B=R/'scratch/transceiver-closed-loop-follower-prepared/closed.spice'
if args.pwl:
 W=R/'scratch/transceiver-closed-loop-follower-pwl';B=R/'scratch/transceiver-closed-loop-follower-pwl-prepared/closed.spice'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def edges(t,v,threshold):
 i=np.flatnonzero((v[:-1]<threshold)&(v[1:]>=threshold))
 return t[i]+(threshold-v[i])*(t[i+1]-t[i])/(v[i+1]-v[i])
m=json.loads((W/'manifest.json').read_text());d=(W/'closed.spice').read_text()
addition='.include /screen/pll/reference_input_buffer.spice\nXREFBUF REFRAW REF VDIV 0 pt_reference_input_buffer\n'
if args.follower:
 assert d==B.read_text()
 prepared=json.loads(B.with_name('manifest.json').read_text());assert sha(B)==prepared['prepared_deck_sha256']
 assert prepared['exact_substitution_reversal_verified']
 assert not re.search(r'^V(?:FB|CLAMP)\s',d,re.M)
else:assert d.count(addition)==1 and d.replace(addition,'').replace('VREF REFRAW 0 ','VREF REF 0 ')==B.read_text()
assert sha(B)==m['source_sha256_before']['/baseline/closed.spice']
assert sha(W/'closed.spice')==m['deck_sha256_before']
roots={'/screen/':P/'analog','/vco/':R/'ip/blocks/analog/wireline_serdes/pll','/wifi/':R/'ip/blocks/analog/wifi_80211b'}
for path,digest in m['source_sha256_before'].items():
 for prefix,root in roots.items():
  if path.startswith(prefix):assert sha(root/path.removeprefix(prefix))==digest
result_path=W/'result.json'
r=dict(status='pending_full_loop_result',declared_change_verified=True,manifest=m,completed_requested_horizon=False,windows=[])
if result_path.exists():
 raw=json.loads(result_path.read_text());assert raw['source_sha256_before']==raw['source_sha256_after']==m['source_sha256_before'] and raw['deck_unchanged']
 for ext,digest in raw['artifacts_sha256'].items():assert sha(W/('closed'+ext))==digest
 r['run_record']=raw;log=(W/'closed.log').read_text()
 failure=re.search(r'Timestep too small; time = ([0-9.e+-]+)',log)
 r['failure_time_ns']=float(failure.group(1))*1e9 if failure else None
 wave=W/'closed.dat'
 if wave.exists():
  with wave.open() as f:header=f.readline().lower().split()
  expected=['time','cml','d1','d2','d3','d4','d5','d6','d7','v(fb)','v(xrx.gate)','i(vdiv)','v(up)','v(dn)','v(ctrl)','v(xfilt.z)','i(vsense)','v(ref)']
  if args.follower:expected+=['v(dummy)','i(vdrv)','i(vdummy)','v(bdn)','v(bdp)','v(xbuf.x)','v(xbuf.t)','i(v.xcp.vp)','i(v.xcp.vn)']
  assert header==expected
  a=np.loadtxt(wave,skiprows=1);assert a.shape[1]==len(expected) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
  t=a[:,0];r['actual_stop_ns']=float(t[-1]*1e9)
  r['control_excursions']=[]
  for start in (0.,100e-9):
   w=a[a[:,0]>=start];kmin=int(np.argmin(w[:,14]));kmax=int(np.argmax(w[:,14]))
   r['control_excursions'].append(dict(start_ns=start*1e9,stop_ns=float(w[-1,0]*1e9),minimum_v=float(w[kmin,14]),minimum_time_ns=float(w[kmin,0]*1e9),maximum_v=float(w[kmax,14]),maximum_time_ns=float(w[kmax,0]*1e9)))
  done=raw['returncode']==0 and not raw['timed_out'] and 'aborted' not in log.lower() and t[-1]+1e-21>=3201e-9
  r['completed_requested_horizon']=bool(done)
  for lo,hi in ((100,200),(500,600),(1100,1200),(2000,2100),(3000,3100)):
   if t[-1]<hi*1e-9:continue
   w=a[(t>=lo*1e-9)&(t<=hi*1e-9)];vt=w[:,0];e=edges(vt,w[:,1],0)
   r['windows'].append(dict(window_ns=[lo,hi],vco_rising_edges=len(e),vco_frequency_hz=float((len(e)-1)/(e[-1]-e[0])) if len(e)>2 else None,control_range_v=[float(w[:,14].min()),float(w[:,14].max())],pump_charge_fc=float(np.trapezoid(w[:,16],vt)*1e15),lna_gate_range_v=[float(w[:,10].min()),float(w[:,10].max())]))
  if args.follower:
   residual=a[:,header.index('i(v.xcp.vp)')]-a[:,header.index('i(v.xcp.vn)')]-a[:,16]
   r['pump_kcl_max_error_a']=float(np.max(abs(residual)));assert r['pump_kcl_max_error_a']<1e-9
   for window in r['windows']:
    lo,hi=window['window_ns'];w=a[(t>=lo*1e-9)&(t<=hi*1e-9)];vt=w[:,0]
    dummy=w[:,header.index('v(dummy)')];power=-3.3*w[:,header.index('i(vdrv)')]
    window['dummy_range_v']=[float(dummy.min()),float(dummy.max())]
    window['driver_supply_power_w']=float(np.trapezoid(power,vt)/(vt[-1]-vt[0]))
  fb=edges(t,a[:,9],1.65);ref=edges(t,a[:,17],1.65)
  fb=fb[fb>=100e-9];ref=ref[ref>=100e-9]
  # Pair by ordinal, never modulo the reference period; cycle slips are not hidden.
  n=min(len(fb),len(ref));r['phase_observation']=dict(reference_edge_count=len(ref),feedback_edge_count=len(fb),ordered_feedback_minus_reference_ns=((fb[:n]-ref[:n])*1e9).tolist(),reference_edge_times_ns=(ref[:n]*1e9).tolist())
  if n>=21:
   # Keep ordinal pairing, including any startup offset; do not wrap phase.
   rt=ref[:n][-21:];ft=fb[:n][-21:];phase=ft-rt
   x=rt-rt[0];slope,intercept=np.polyfit(x,phase,1);residual=phase-(slope*x+intercept)
   r['late_phase_diagnostic']=dict(paired_edges=21,window_ns=[float(rt[0]*1e9),float(rt[-1]*1e9)],reference_frequency_hz=float(20/(rt[-1]-rt[0])),feedback_frequency_hz=float(20/(ft[-1]-ft[0])),phase_drift_ns=float((phase[-1]-phase[0])*1e9),phase_slope_s_per_s=float(slope),detrended_phase_peak_to_peak_ps=float(np.ptp(residual)*1e12),limitations='Last21 ordinal edge pairs; deterministic residual is not intrinsic jitter. No lock threshold allocated or asserted. Partial-run tail may be a failure neighborhood.')
  r['status']='completed_seeded_full_loop_diagnostic' if done else 'failed_full_loop_partial_waveform'
 else:r['status']='terminal_without_waveform'
r['limitations']=['Seeded/prebiased operation, ideal reference/bias/supplies, nominal models; no cold-start or variation qualification.', 'Ordered edge pairing has startup-dependent alignment; it is a diagnostic phase history, not a lock detector.', 'Deterministic frequency/phase trajectories do not establish random jitter, intrinsic phase noise, stability or silicon behavior.']
(P/('evidence/closed-loop-follower-pwl-screen.json' if args.pwl else 'evidence/closed-loop-follower-screen.json' if args.follower else 'evidence/closed-loop-buffered-screen.json')).write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({k:r[k] for k in ('status','completed_requested_horizon','windows')},indent=2))
