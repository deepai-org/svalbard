#!/usr/bin/env python3
"""Same-window comparison; digital capture success is not analog accuracy."""
import hashlib,json,sys
include_same="--same-history" in sys.argv
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';D=R/'scratch/transceiver-adc-shared-iq-frames';B=R/'scratch/transceiver-adc-sar8-reference-compensated'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
dual=json.loads((D/'result.json').read_text());audit=json.loads((P/'evidence/adc-shared-iq-frames.json').read_text());assert audit['completed'] and audit['provenance']==dual
base=json.loads((B/'result.json').read_text());rows=[]
inputs=[('shared_IQ',D/'frames.dat',dual)]+[(c['name'],B/(c['name']+'.dat'),c) for c in base['cases']]
if include_same:
 S=R/'scratch/transceiver-adc-shared-iq-same';sa=P/'evidence/adc-shared-iq-same.json'
 if not (S/'result.json').exists() or not sa.exists():print('Same-history comparison pending');raise SystemExit(0)
 sr=json.loads((S/'result.json').read_text());sa=json.loads(sa.read_text())
 if not sa['completed']:print('Same-history comparison incomplete; no combined comparison generated');raise SystemExit(0)
 assert sa['provenance']==sr
 inputs.append(('shared_IQ_same',S/'frames.dat',sr))
for label,path,record in inputs:
 assert record['returncode']==0 and not record['timed_out'] and sha(path)==record['artifacts_sha256']['.dat']
 with path.open() as f:h=f.readline().lower().split()
 a=np.loadtxt(path,skiprows=1);assert np.isfinite(a).all() and a[-1,0]+1e-21>=209.9e-9
 steps=[];codes=[];qcodes=[];powers=[]
 for hold in (70,120,170):
  cap=a[(a[:,0]>=(hold+39.3)*1e-9)&(a[:,0]<=(hold+39.7)*1e-9)]
  bits=cap[:,[h.index(f'v(d{i})') for i in range(8)]];codes.append(np.unique((bits>1.65).astype(int)@2**np.arange(8)).tolist())
  if 'v(q_d0)' in h:
   qb=cap[:,[h.index(f'v(q_d{i})') for i in range(8)]];qcodes.append(np.unique((qb>1.65).astype(int)@2**np.arange(8)).tolist())
  active=a[(a[:,0]>=hold*1e-9)&(a[:,0]<=(hold+39.7)*1e-9)];t=active[:,0];powers.append(float(-3.3*np.trapezoid(active[:,h.index('i(vrefsup)')],t)/(t[-1]-t[0])))
  for bit in range(7,-1,-1):
   lo=hold+.2+5*(7-bit);hi=hold+.35+5*(7-bit);w=a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)];assert len(w)>1;vh=w[:,h.index('v(vh)')];vl=w[:,h.index('v(vl)')]
   steps.append(dict(window_ns=[lo,hi],span_mean_v=float(np.mean(vh-vl)),span_motion_v=float(np.ptp(vh-vl)),high_error_v=float(abs(vh-2.15).max()),low_error_v=float(abs(vl-1.15).max())))
 lo_span=min(x['span_mean_v'] for x in steps);hi_span=max(x['span_mean_v'] for x in steps)
 rows.append(dict(case=label,best_constant_additive_span_correction_v=1-(lo_span+hi_span)/2,minimum_worst_mean_span_error_after_constant_correction_v=(hi_span-lo_span)/2,captured_I_or_single_codes=codes,captured_Q_codes=qcodes,reference_supply_frame_power_w=powers,decision_span_range_v=[min(x['span_mean_v'] for x in steps),max(x['span_mean_v'] for x in steps)],worst_decision_span_motion_v=max(x['span_motion_v'] for x in steps),worst_high_error_v=max(x['high_error_v'] for x in steps),worst_low_error_v=max(x['low_error_v'] for x in steps),waveform_sha256=sha(path)))
out=dict(status='shared_reference_loading_comparison',cases=rows,limitations=['Both baseline histories are separate single-channel runs, not simultaneous channels.', 'Decision-window sample means, not ENOB/noise or aperture-weighted accuracy.', 'Only selected synchronous histories; timing skew, mismatch and arbitrary signals remain unqualified.', 'Power covers the reference supply only; not an accurate total-chip budget or qualified sharing savings.', 'Constant-correction result is a minimax mathematical offset of recorded span means; not a physical trim, per-code calibration, or bound on a redesigned reference.'])
(P/('evidence/adc-shared-history-comparison.json' if include_same else 'evidence/adc-shared-reference-comparison.json')).write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows,indent=2))
