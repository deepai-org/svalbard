"""Separate nominal target error from excursion about independently measured DC."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';E=P/'evidence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
fp=E/'reference-hybrid-frames.json';dp=E/'reference-hybrid.json'
f=json.loads(fp.read_text());dc=json.loads(dp.read_text());assert f['completed'] and dc['completed']
out=dict(completed=False,input_sha256={str(p.relative_to(R)):sha(p) for p in (fp,dp)},cases={})
for name,root in [('baseline',R/'scratch/transceiver-cdac-probe-reltol/probed'),('candidate',R/'scratch/transceiver-reference-hybrid-frames')]:
 for ext,h in f['cases'][name]['artifacts_sha256'].items():assert sha(root/('frames'+ext))==h
 with (root/'frames.dat').open() as stream:header=stream.readline().lower().split()
 a=np.loadtxt(root/'frames.dat',skiprows=1,usecols=[0,header.index('v(vh)'),header.index('v(vl)')]);t=a[:,0]
 assert np.isfinite(a).all() and np.all(np.diff(t)>0) and t[-1]+1e-21>=209.9e-9
 rows=[]
 for rail,col,target in [('h',1,2.15),('l',2,1.15)]:
  entry=next(x for x in dc['cases'] if x['rail']=='V'+rail.upper())
  offset=next(x['error_v'] for x in entry['values'] if x['case']==name);op=target+offset
  windows=[]
  for hold in (70,120,170):
   for bit in range(8):
    lo=(hold+5*bit+.2)*1e-9;hi=(hold+5*bit+.35)*1e-9
    tt=np.r_[lo,t[(t>lo)&(t<hi)],hi];y=np.interp(tt,t,a[:,col])
    original=next(x for x in f['cases'][name]['decisions'] if x['rail']==rail and x['hold_ns']==hold and x['bit_index']==bit)
    assert abs(float(abs(y-target).max())-original['max_error_v'])<1e-12
    windows.append(dict(hold_ns=hold,bit_index=bit,min_deviation_from_dc_v=float((y-op).min()),max_deviation_from_dc_v=float((y-op).max()),max_abs_deviation_from_dc_v=float(abs(y-op).max()),max_target_error_v=original['max_error_v']))
  rows.append(dict(rail=rail,dc_output_v=op,dc_target_offset_v=offset,windows=windows,worst_deviation_from_dc_v=max(w['max_abs_deviation_from_dc_v'] for w in windows),worst_target_error_v=max(w['max_target_error_v'] for w in windows)))
 out['cases'][name]=rows
out.update(completed=True,limitations=['DC origin comes from the independent unloaded nominal operating-point fixture; deviation is not an isolated causal switching contribution.', 'No offset calibration circuit or corrected ADC performance is demonstrated.', 'Original target-error failures and power regressions remain; no candidate promotion or new acceptance threshold.'])
(E/'reference-hybrid-offsets.json').write_text(json.dumps(out,indent=2)+'\n')
for name,rows in out['cases'].items():print(name,[(x['rail'],x['worst_target_error_v'],x['worst_deviation_from_dc_v']) for x in rows])
