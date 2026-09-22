"""Windowed internal-device diagnostics, gated on observation reproduction."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';E=P/'evidence/sar-reference-devices.json';W=R/'scratch/transceiver-sar-reference-devices'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def negative_duration(t,y):
 # Exact duration below zero for piecewise-linear interpolation of saved samples.
 left=y[:-1];right=y[1:];dt=np.diff(t)
 fraction=np.zeros_like(dt)
 fraction[(left<0)&(right<0)]=1.
 down=(left>=0)&(right<0);up=(left<0)&(right>=0)
 fraction[down]=-right[down]/(left[down]-right[down])
 fraction[up]=-left[up]/(right[up]-left[up])
 return float(np.sum(dt*fraction))
assert negative_duration(np.array([0.,2.]),np.array([-1.,3.]))==.5
assert negative_duration(np.array([0.,2.]),np.array([3.,-1.]))==.5
assert negative_duration(np.array([0.,1.,3.]),np.array([-1.,0.,1.]))==1.
assert negative_duration(np.array([0.,1.,3.]),np.zeros(3))==0.
assert negative_duration(np.array([0.,1.,3.]),-np.ones(3))==3.
audit=json.loads(E.read_text());out=dict(completed=False,status='awaiting_qualified_observation',source_sha256=sha(E),limitations=['VDS minus VDSAT is a model operating-region indicator, not measured loop gain or phase margin.','ID includes multiplicity and is not total terminal current; do not use alone for rail charge balance.','Negative reported VDS flags departure from the selected forward-conduction probe convention.','Nominal timing and input sequence only; no process/mismatch/noise guarantee.'])
if audit['completed'] and audit['reproduction_pass']:
 p=W/'baseline.dat';assert sha(p)==audit['waveform_sha256']
 with p.open() as f:h=f.readline().lower().split()
 a=np.loadtxt(p,skiprows=1);t=a[:,0];assert np.isfinite(a).all() and np.all(np.diff(t)>0)
 rows=[]
 for hold in (70,120,170):
  for bit in range(7,-1,-1):
   lo=hold+5*(7-bit);hi=lo+5 if bit else hold+39
   tt=np.r_[lo*1e-9,t[(t>lo*1e-9)&(t<hi*1e-9)],hi*1e-9];devices=[]
   for rail in ('xhigh','xlow'):
    for dev in ('xin','xip','xt','xmp','xmn','xout','xload'):
     def vector(param):return np.interp(tt,t,a[:,h.index(f'@m.xref.{rail}.{dev}.m0[{param}]')])
     current=vector('id');vds=vector('vds');margin=vds-vector('vdsat');k=int(np.argmin(margin));clock=(lo+.5)*1e-9
     devices.append(dict(rail=rail,device=dev,min_margin_v=float(margin[k]),minimum_time_ns=float(tt[k]*1e9),margin_at_clock_v=float(np.interp(clock,tt,margin)),min_reported_vds_v=float(vds.min()),current_min_a=float(current.min()),current_max_a=float(current.max()),current_at_clock_a=float(np.interp(clock,tt,current)),fraction_time_margin_negative=negative_duration(tt,margin)/(tt[-1]-tt[0])))
   rows.append(dict(hold_ns=hold,bit=bit,window_ns=[lo,hi],devices=devices))
 out.update(completed=True,status='qualified_observation_device_diagnostic',windows=rows)
(P/'evidence/sar-reference-device-windows.json').write_text(json.dumps(out,indent=2)+'\n');print(out['status'])
if out['completed']:
 for rail in ('xhigh','xlow'):
  for dev in ('xin','xip','xt','xmp','xmn','xout','xload'):
   cells=[d for w in out['windows'] for d in w['devices'] if d['rail']==rail and d['device']==dev]
   print(rail,dev,'minimum VDS-VDSAT',min(x['min_margin_v'] for x in cells))
