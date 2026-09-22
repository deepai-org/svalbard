#!/usr/bin/env python3
import hashlib,json,re,sys
recovery="--recovery" in sys.argv
from pathlib import Path
import numpy as np
from tx_cycle_metrics import cycle_amplitude
# Exported15-digit timestamps may end a few1e-23s below requested horizon.
ENDPOINT_TOL_S=1e-21  # Only endpoint comparison; never retime waveform samples.
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/('scratch/transceiver-tx-selfbias-recovery' if recovery else 'scratch/transceiver-tx-selfbias-dynamic');B=R/'scratch/transceiver-tx-buffered-lo';M=R/'scratch/transceiver-tx-ring-settling'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if not (W/'result.json').exists():print('Pending dynamic self-bias cases');raise SystemExit(0)
m=json.loads((W/'manifest.json').read_text());r=json.loads((W/'result.json').read_text());assert m['source_sha256_before']==r['source_sha256_before']==r['source_sha256_after'];src=B/'nmos_c255.spice';assert sha(src)==m['baseline_deck_sha256'] and sha(M/'settling.dat')==m['measured_wave_sha256']
with (M/'settling.dat').open() as f:hm=f.readline().lower().split()
am=np.loadtxt(M/'settling.dat',skiprows=1);start=540e-9 if recovery else 590e-9;tt=np.r_[start,am[(am[:,0]>start)&(am[:,0]<600e-9),0],600e-9]
assert [(c['name'],c['injection_a']) for c in r['cases']]==[('zero',0),('minus',-3e-6),('plus',3e-6)];rows=[];case_status=[]
for c in r['cases']:
 name=c['name'];d=(W/(name+'.spice')).read_text();assert sha(W/(name+'.spice'))==c['deck_sha256_before']
 for source,node,orig,col,pulse in [('VLO','RAWP','LOIN','v(cp)','PULSE(0 3.3 1n 20p 20p 180p 400p)'),('VLOB','RAWN','LOBIN','v(cn)','PULSE(3.3 0 1n 20p 20p 180p 400p)')]:
  match=re.search('^'+source+' '+node+r' 0 PWL\(([^\n]+)\)$',d,re.M);assert match;pairs=np.asarray([float(x) for x in match.group(1).split()]).reshape(-1,2)
  assert np.array_equal(pairs[:,0],tt-start) and np.allclose(pairs[:,1],np.interp(tt,am[:,0],am[:,hm.index(col)]),atol=1e-14,rtol=0)
  d=d.replace(match.group(0),f'{source} {orig} 0 {pulse}')
 for line in ['CCP RAWP LOIN 200f','CCN RAWN LOBIN 200f','RFBP LOIN XLP.MID 100k','RFBN LOBIN XLN.MID 100k',f"IEP 0 LOIN PWL(0 0 2n 0 2.1n {c['injection_a']:.17g})",f"IEN 0 LOBIN PWL(0 0 2n 0 2.1n {c['injection_a']:.17g})"]:
  if recovery and line.startswith(('IEP ','IEN ')):
   line=line[:-1]+f" 20n {c['injection_a']:.17g} 20.1n 0)"
  assert d.count(line+'\n')==1;d=d.replace(line+'\n','')
 if recovery:d=d.replace('tran 2p 60n 0 2p','tran 2p 10n 0 2p').replace(' v(XLP.MID) v(XLN.MID)\n','\n')
 assert d.replace(f'/work/{name}.dat','/work/nmos_c255.dat')==src.read_text()
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 log=(W/(name+'.log')).read_text().lower()
 failure=re.search(r'timestep too small; time = ([0-9.e+-]+)',log)
 state=dict(name=name,completed=False,returncode=c['returncode'],timed_out=c['timed_out'],failure_time_s=float(failure.group(1)) if failure else None)
 case_status.append(state)
 if not (W/(name+'.dat')).exists():
  state['waveform_available']=False
  continue
 with (W/(name+'.dat')).open() as f:h=f.readline().lower().split()
 assert h==['time']+next(l for l in d.splitlines() if l.startswith('save ')).lower().split()[1:]+(['v(xlp.mid)','v(xln.mid)'] if recovery else [])
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.ndim==2 and a.shape[1]==len(h) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
 state.update(waveform_available=True,actual_stop_ns=float(a[-1,0]*1e9),completed=bool(c['returncode']==0 and not c['timed_out'] and 'aborted' not in log and a[-1,0]+ENDPOINT_TOL_S>=(60e-9 if recovery else 10e-9)))
 for lo,hi in ([(6,10),(16,20),(26,30),(56,60)] if recovery else [(6,10)]):
  if a[-1,0]+ENDPOINT_TOL_S<hi*1e-9:continue
  ar=a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)];t=ar[:,0]
  def v(k):return ar[:,h.index(k)]
  def avg(y):return float(np.trapezoid(y,t)/(t[-1]-t[0]))
  y=v('v(lo)');ix=np.where((y[:-1]<1.65)&(y[1:]>=1.65))[0];cross=t[ix]+(t[ix+1]-t[ix])*(1.65-y[ix])/(y[ix+1]-y[ix]);amps=cycle_amplitude(t,v('v(rfp)')-v('v(rfn)'),cross)
  rows.append(dict(name=name,window_ns=[lo,hi],first_stage_ranges_v={k:[float(v(k).min()),float(v(k).max())] for k in ['v(xlp.mid)','v(xln.mid)']} if recovery else None,complete_cycles=len(amps),rf_fundamental_peak_range_v=[min(amps),max(amps)] if amps else None,input_common_mode_mean_v=avg((v('v(loin)')+v('v(lobin)'))/2),lo_range_v=[float(y.min()),float(y.max())],buffer_power_w=-3.3*avg(v('i(vlobuf)'))))
out=dict(status='completed_dynamic_selfbias_diagnostic' if all(c['completed'] for c in case_status) else 'incomplete_dynamic_selfbias_diagnostic',endpoint_tolerance_s=ENDPOINT_TOL_S,case_status=case_status,cases=rows,provenance=r,limitations=['Recorded oscillator-output voltage replay removes bidirectional oscillator loading; no autonomous stability claim.', 'Equal injected currents are scenarios, not process/mismatch bounds; ideal supplies and passives.', 'Finite OP-initialized replay; observed windows alone do not establish all-time stability or asymmetric disturbance tolerance.'])
(P/('evidence/tx-selfbias-recovery.json' if recovery else 'evidence/tx-selfbias-dynamic.json')).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows,indent=2))
