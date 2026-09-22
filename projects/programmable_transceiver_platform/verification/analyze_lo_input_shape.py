"""Ring-cycle harmonic shape grouped by observed output-edge bins."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';B=R/'scratch/transceiver-lo-receiver-replay-prepared';E=P/'evidence/lo-input-dwell.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
d=json.loads(E.read_text());assert d['completed'] and sha(B/'parent_samples.npy')==d['parent_samples_sha256'];a=np.load(B/'parent_samples.npy');m=json.loads((B/'manifest.json').read_text());h=m['sample_columns'];t=a[:,0]
y=a[:,h.index('v(p)')]-a[:,h.index('v(n)')];k=np.flatnonzero((y[:-1]<0)&(y[1:]>=0));ring=t[k]-y[k]*np.diff(t)[k]/np.diff(y)[k];rows=[]
for leg in d['legs']:
 signal=a[:,h.index('v(b'+leg['leg']+')')];measurements=[]
 for c in leg['cycles']:
  lo=c['start_ns']*1e-9;j=int(abs(ring-lo).argmin());assert abs(ring[j]-lo)<1e-18;lo=ring[j];hi=ring[j+1]
  first,last=np.searchsorted(t,[lo,hi]);tt=np.r_[lo,t[first:last],hi];tt=np.unique(tt);yy=np.interp(tt,t,signal);phase=2*np.pi*(tt-lo)/(hi-lo);mean=np.trapezoid(yy,tt)/(hi-lo);amps=[]
  for harmonic in (1,2,3):
   z=2*np.trapezoid((yy-mean)*np.exp(-1j*harmonic*phase),tt)/(hi-lo);amps.append(float(abs(z)))
  measurements.append(dict(output_rises=c['output_rises'],mean_v=float(mean),harmonic_peak_v=amps))
 groups={}
 for count in sorted(set(x['output_rises'] for x in measurements)):
  group=[x for x in measurements if x['output_rises']==count];v=np.array([x['harmonic_peak_v'] for x in group]);groups[str(count)]=dict(cycles=len(group),harmonic_peak_min_v=v.min(axis=0).tolist(),harmonic_peak_max_v=v.max(axis=0).tolist(),harmonic_peak_mean_v=v.mean(axis=0).tolist(),mean_voltage_range_v=[min(x['mean_v'] for x in group),max(x['mean_v'] for x in group)])
 rows.append(dict(leg=leg['leg'],groups=groups))
out=dict(completed=True,dwell_evidence_sha256=sha(E),parent_samples_sha256=d['parent_samples_sha256'],legs=rows,limitations=['Per-ring-cycle Fourier projections on native samples are waveform-shape diagnostics, not stationary spectrum or causal attribution.', 'Zero-edge bins can include phase-bin migration; earlier long-gap observations remain stronger missing-pulse evidence.', 'Ideal-sine tests differ in source and loading; harmonic correlation alone does not select a circuit fix.'])
(P/'evidence/lo-input-shape.json').write_text(json.dumps(out,indent=2)+'\n')
for row in rows:print(row)
