#!/usr/bin/env python3
"""Reference accuracy at decision times, separate from full-frame extrema."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
parser=argparse.ArgumentParser();parser.add_argument('--reservoir',action='store_true');parser.add_argument('--compensated',action='store_true');parser.add_argument('--output2',action='store_true');args=parser.parse_args()
tag='sar8-reference-output2' if args.output2 else 'sar8-reference-compensated' if args.compensated else 'sar8-reference-reservoir' if args.reservoir else 'sar8-reference-driver'
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/('scratch/transceiver-adc-'+tag)
audit=json.loads((P/('evidence/adc-'+tag+'-screen.json')).read_text());rows=[]
for c in audit['cases']:
 file=W/(c['name']+'.dat');assert hashlib.sha256(file.read_bytes()).hexdigest()==c['artifacts_sha256']['.dat']
 a=np.loadtxt(file,skiprows=1);frames=[]
 for f in c['frames']:
  hold=f['hold_ns'];steps=[]
  for bit in range(7,-1,-1):
   # Match the existing comparator pre-evaluation window.
   lo=hold+.2+5*(7-bit);hi=hold+.35+5*(7-bit)
   w=a[(a[:,0]>=lo*1e-9)&(a[:,0]<=hi*1e-9)];assert len(w)>1
   vh=w[:,43];vl=w[:,44]
   steps.append(dict(bit=bit,window_ns=[lo,hi],high_mean_v=float(vh.mean()),low_mean_v=float(vl.mean()),span_mean_v=float(np.mean(vh-vl)),high_max_error_mv=float(np.max(abs(vh-2.15))*1e3),low_max_error_mv=float(np.max(abs(vl-1.15))*1e3),span_peak_to_peak_mv=float(np.ptp(vh-vl)*1e3)))
  frames.append(dict(hold_ns=hold,input_v=f['input_v'],steps=steps))
 rows.append(dict(name=c['name'],frames=frames,waveform_sha256=c['artifacts_sha256']['.dat']))
r=dict(status='reference_decision_window_audit',cases=rows,pending=audit['pending_or_incomplete_cases'],limitations=['Window chosen before comparator evaluation; not a full aperture/jitter analysis.', 'No attribution of total code error solely to reference error; sampling/static/comparator effects coexist.', 'Voltage targets remain ideal and only selected nominal streams tested.'])
(P/('evidence/adc-reference'+('-output2' if args.output2 else '-compensated' if args.compensated else '-reservoir' if args.reservoir else '')+'-decision-windows.json')).write_text(json.dumps(r,indent=2)+'\n')
for c in rows:
 steps=[s for f in c['frames'] for s in f['steps']];print(c['name'],'decision span min/max',min(s['span_mean_v'] for s in steps),max(s['span_mean_v'] for s in steps),'high worst mV',max(s['high_max_error_mv'] for s in steps),'low worst mV',max(s['low_max_error_mv'] for s in steps))
