#!/usr/bin/env python3
"""Separate pre-turnoff acquisition error from the net turnoff interval change."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
parser=argparse.ArgumentParser();parser.add_argument('--fast-comp',action='store_true');args=parser.parse_args()
tag='sar8-mim-fast-comp' if args.fast_comp else 'sar8-mim-frames'
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/('scratch/transceiver-adc-'+tag)
audit=json.loads((P/('evidence/adc-'+tag+'-screen.json')).read_text());cases=[]
for c in audit['cases']:
 name=c['name'];file=W/(name+'.dat');assert hashlib.sha256(file.read_bytes()).hexdigest()==c['artifacts_sha256']['.dat']
 a=np.loadtxt(file,skiprows=1);frames=[]
 for f in c['frames']:
  h=f['hold_ns'];vin=f['input_v'];points=[]
  for offset in (-5,-2,-1,-.2,-.01,0,.05,.1,.2,.35):
   held=float(np.interp((h+offset)*1e-9,a[:,0],a[:,1]-a[:,2]));driver=float(np.interp((h+offset)*1e-9,a[:,0],a[:,28]-a[:,29]))
   points.append(dict(offset_ns=offset,held_v=held,driver_v=driver,held_error_v=held-vin))
  pre=next(x for x in points if x['offset_ns']==0);post=points[-1]
  w=a[(a[:,0]>=(h-1)*1e-9)&(a[:,0]<=h*1e-9)];v=w[:,1]-w[:,2]
  frames.append(dict(hold_ns=h,input_v=vin,trajectory=points,pre_turnoff_error_v=pre['held_error_v'],post_turnoff_error_v=post['held_error_v'],net_turnoff_interval_change_v=post['held_v']-pre['held_v'],last_track_ns_error_range_v=[float(v.min()-vin),float(v.max()-vin)],last_track_ns_peak_to_peak_v=float(np.ptp(v))))
 cases.append(dict(name=name,frames=frames,waveform_sha256=c['artifacts_sha256']['.dat']))
r=dict(status='completed_stream_acquisition_diagnostic',cases=cases,limitations=['Net turnoff interval includes feedthrough, channel charge, changing drive and continuing settling; not an isolated charge-injection measurement.', 'Observed overshoot and timing sensitivity do not by themselves establish small-signal loop stability or phase margin.', 'Only completed streams are analyzed; no full ADC qualification.'])
(P/('evidence/adc-sar8-acquisition'+('-fast-comp' if args.fast_comp else '')+'-diagnostic.json')).write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps([dict(name=c['name'],pre_error_mv=[f['pre_turnoff_error_v']*1e3 for f in c['frames']],turnoff_change_mv=[f['net_turnoff_interval_change_v']*1e3 for f in c['frames']],last_ns_swing_mv=[f['last_track_ns_peak_to_peak_v']*1e3 for f in c['frames']]) for c in cases],indent=2))
