#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-tx-lo-switching';B=R/'scratch/transceiver-tx-tg-dc'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((W/'manifest.json').read_text());assert sha(B/'r50_lo1.spice')==m['baseline_deck_sha256']
out=dict(status='pending',cases=[],limitations=['Ideal2.5GHz LO, fixed DAC code, nominal model and ideal biases. Not autonomous timing or modulated RF qualification.', 'Signed ideal-source energy is not driver dissipation; returned charge must not be treated as free physical drive.', 'One1pF output-load scenario, no mismatch/noise/reconstruction/IQ or package qualification.'])
if (W/'result.json').exists():
 r=json.loads((W/'result.json').read_text());assert r['source_sha256_before']==r['source_sha256_after']==m['source_sha256_before']
 assert [c['name'] for c in r['cases']]==['nmos_c128','nmos_c255','tg_c128','tg_c255']
 for c in r['cases']:
  name=c['name'];d=(W/(name+'.spice')).read_text();assert sha(W/(name+'.spice'))==c['deck_sha256_before']
  for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
  original=d.split('CRP RFP 0 1p\n')[0].replace(f"VCODE CODE 0 {c['code']}\n",'VCODE CODE 0 0\n').replace('VLO LO 0 PULSE(0 3.3 1n 20p 20p 180p 400p)','VLO LO 0 3.3').replace('VLOB LOB 0 PULSE(3.3 0 1n 20p 20p 180p 400p)','VLOB LOB 0 0.0')
  if c['variant']=='nmos':original=original.replace('XM OP ON RFP RFN LO LOB 0 pt_tx_commutator\n','XM OP ON RFP RFN LO LOB VDD 0 pt_tx_commutator_tg\n')
  assert original==(B/'r50_lo1.spice').read_text().split('.control')[0]
  assert 'CRN RFN 0 1p\n' in d and 'tran 2p 10n 0 2p\n' in d
  log=(W/(name+'.log')).read_text().lower();assert c['returncode']==0 and not c['timed_out'] and 'aborted' not in log
  with (W/(name+'.dat')).open() as f:h=f.readline().lower().split()
  assert h==['time']+m['vectors'].lower().split()
  a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert np.isfinite(a).all() and np.all(np.diff(a[:,0])>0) and a[-1,0]>=10e-9
  # Strictly increasing times: interpolate only the two exact integration bounds.
  t=np.r_[6e-9,a[(a[:,0]>6e-9)&(a[:,0]<10e-9),0],10e-9]
  def v(k):return np.interp(t,a[:,0],a[:,h.index(k)])
  def integ(y):return float(np.trapezoid(y,t))
  rf=v('v(rfp)')-v('v(rfn)');omega=2*np.pi*2.5e9
  fundamental=2/4e-9*abs(integ(rf*np.cos(omega*t))+1j*integ(rf*np.sin(omega*t)))
  current=[v('i(vlo)'),v('i(vlob)')];volt=[v('v(lo)'),v('v(lob)')]
  out['cases'].append(dict(name=name,completed=True,actual_stop_ns=float(a[-1,0]*1e9),window_ns=[6,10],rf_fundamental_peak_v=float(fundamental),rf_peak_to_peak_v=float(np.ptp(rf)),lo_peak_absolute_current_a=max(float(abs(x).max()) for x in current),lo_sum_absolute_charge_per_cycle_c=sum(integ(abs(x)) for x in current)/10,lo_signed_delivered_energy_per_cycle_j=-sum(integ(x*y) for x,y in zip(current,volt))/10))
 out['status']='completed_ideal_LO_diagnostic';out['provenance']=r
(P/'evidence/tx-lo-switching.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='provenance'},indent=2))
