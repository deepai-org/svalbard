"""Late zero-input baseband periodicity; deterministic spectra are not noise."""
import argparse,hashlib,json
ap=argparse.ArgumentParser();ap.add_argument("--path-nodes",action="store_true");args=ap.parse_args()
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-latest-rf-loop-selective';E=P/'evidence/latest-rf-loop-selective.json'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for x in iter(lambda:f.read(1024*1024),b''):h.update(x)
 return h.hexdigest()
e=json.loads(E.read_text());assert e['completed'] and e['actual_stop_ns']>=8001-1e-8
names=['v(fip)','v(fin)','v(fqp)','v(fqn)','v(ctrl)','v(lg)','v(ls)'];rows=[];digest=hashlib.sha256()
if args.path_nodes:names+=['v(mip)','v(min)','v(mqp)','v(mqn)','v(oip)','v(oin)','v(oqp)','v(oqn)','v(p)','v(n)','v(rf)']
with (W/'latest.dat').open('rb') as f:
 header=f.readline();digest.update(header);h=header.decode().lower().split();cols=[0]+[h.index(n) for n in names]
 for line in f:
  digest.update(line)
  if float(line.split(None,1)[0])<6.399e-6:continue
  parts=line.split();assert len(parts)==len(h);rows.append([float(parts[k]) for k in cols])
assert digest.hexdigest()==e['provenance']['artifacts_sha256']['.dat']
a=np.array(rows);t=a[:,0];assert np.isfinite(a).all() and np.all(np.diff(t)>0)
signals={'i':a[:,1]-a[:,2],'q':a[:,3]-a[:,4],'ctrl':a[:,5],'lg':a[:,6],'ls':a[:,7]};windows=[];period=51.2e-9
if args.path_nodes:
 def v(n):return a[:,1+names.index(n)]
 for label,pos,neg in [('mixer_i','v(mip)','v(min)'),('mixer_q','v(mqp)','v(mqn)'),('lo_i','v(oip)','v(oin)'),('lo_q','v(oqp)','v(oqn)'),('ring','v(p)','v(n)')]:
  signals[label+'_diff']=v(pos)-v(neg);signals[label+'_cm']=(v(pos)+v(neg))/2
 signals['rf']=v('v(rf)')
for lo in (6400,6912,7424):
 hi=lo+512;tt=np.linspace(lo*1e-9,hi*1e-9,51201);assert t[0]<=tt[0] and t[-1]>=tt[-1];result={}
 for n,y in signals.items():
  yy=np.interp(tt,t,y);mean=float(np.trapezoid(yy,tt)/(tt[-1]-tt[0]));ac=yy-mean
  harmonics=[]
  for k in range(1,9):
   phase=2*np.pi*k*(tt-tt[0])/period
   cosine=2*np.trapezoid(ac*np.cos(phase),tt)/(tt[-1]-tt[0]);sine=2*np.trapezoid(ac*np.sin(phase),tt)/(tt[-1]-tt[0]);harmonics.append(float(np.hypot(cosine,sine)))
  # Compare samples one whole reference period apart on the same10ps grid.
  delta=yy[5120:]-yy[:-5120]
  result[n]=dict(mean_v=mean,peak_to_peak_v=float(np.ptp(yy)),reference_harmonic_peak_v=harmonics,period_shift_rms_difference_v=float(np.sqrt(np.mean(delta**2))))
 windows.append(dict(window_ns=[lo,hi],signals=result))
out=dict(completed=True,parent_evidence_sha256=sha(E),waveform_sha256=digest.hexdigest(),windows=windows,limitations=['Uniform10ps interpolation; harmonic projection over ten nominal reference periods, not general spectral/noise analysis.', 'Coincident periodicity does not prove a unique coupling path.', 'Seeded zero-RF nominal loop, ideal bias/supplies and no ADC; no jitter or receiver qualification.'])
(P/'evidence'/('latest-loop-path-nodes.json' if args.path_nodes else 'latest-loop-baseband.json')).write_text(json.dumps(out,indent=2)+'\n')
for w in windows:print(w['window_ns'],{n:(x['peak_to_peak_v'],x['reference_harmonic_peak_v'][0],x['period_shift_rms_difference_v']) for n,x in w['signals'].items()})
