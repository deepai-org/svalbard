"""Static LO chain transfer, explicitly excluding loaded dynamic qualification."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-lo-transfer-dc-v2'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());assert r['sources_before']==r['sources_after'];rows=[];arrays=[]
for c in r['cases']:
 n=c['name'];assert c['returncode']==0
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(n+ext))==h
 assert not any(k in (W/(n+'.log')).read_text().lower() for k in ('error','warning','aborted'))
 with (W/(n+'.dat')).open() as f:assert f.readline().lower().split()==['v-sweep','v(in)','v(xb.mid)','v(pre)','v(out)','i(vdd)']
 a=np.loadtxt(W/(n+'.dat'),skiprows=1);assert a.shape==(501,6) and np.isfinite(a).all()
 if n=='down':a=a[::-1]
 assert np.allclose(a[:,0],np.linspace(1.3,1.8,501),atol=1e-13,rtol=0);arrays.append(a)
 thresholds={}
 for col,label in ((2,'mid'),(3,'pre'),(4,'out')):
  y=a[:,col];k=np.flatnonzero((y[:-1]-1.65)*(y[1:]-1.65)<0);assert len(k)==1;i=k[0];thresholds[label]=float(a[i,0]+(1.65-y[i])*.001/(y[i+1]-y[i]))
 rows.append(dict(direction=n,threshold_inputs_v=thresholds,output_at_observed_bip_extrema_v=[float(np.interp(x,a[:,0],a[:,4])) for x in (1.436633123235521,1.629206891423866)]))
out=dict(completed=True,cases=rows,max_direction_voltage_difference_v=float(abs(arrays[0][:,1:5]-arrays[1][:,1:5]).max()),provenance=r,limitations=['Driven ideal DC input and50fF output capacitance only; AC coupling, self-bias and mixer loading absent.', 'Static threshold crossing does not establish switching speed or duty margin with a~400ps carrier.', 'Measured input extrema bracket static region only; their durations and dynamic internal-node states remain essential.'])
(P/'evidence/lo-transfer-dc.json').write_text(json.dumps(out,indent=2)+'\n');print(rows);print(out['max_direction_voltage_difference_v'])
