"""Self-biased LO input stationary response; scope excludes RF switching."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-lo-selfbias-ac'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());assert r['sources_before']==r['sources_after'];c=r['cases'][0];assert c['returncode']==0
for ext,h in c['artifacts_sha256'].items():assert sha(W/('ac'+ext))==h
assert sha(W/'op.dat')==r['op_sha256'];assert not any(k in (W/'ac.log').read_text().lower() for k in ('error','warning','aborted'))
with (W/'ac.dat').open() as f:assert f.readline().lower().split()==['frequency','ir','ii','mr','mi']
a=np.loadtxt(W/'ac.dat',skiprows=1);assert a.shape==(281,5) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0)
with (W/'op.dat').open() as f:h=f.readline().lower().split()
op=np.loadtxt(W/'op.dat',skiprows=1);op=np.atleast_2d(op);assert np.isfinite(op).all()
values={n:float(op[0,h.index(n)]) for n in ('v(in)','v(xb.mid)','v(pre)','v(out)','i(vdd)')}
response=[]
for f in (1e6,19.53125e6,100e6,2.5e9):
 z=complex(np.interp(np.log10(f),np.log10(a[:,0]),a[:,1]),np.interp(np.log10(f),np.log10(a[:,0]),a[:,2]));response.append(dict(frequency_hz=f,input_gain=float(abs(z)),input_phase_deg=float(np.angle(z,deg=True))))
out=dict(completed=True,provenance=r,operating_point=values,response=response,limitations=['Linearization about static self-bias with actual coupling MIM and100k feedback; not periodic RF transfer, envelope response or settling proof.', 'Final stage50fF only; actual mixer loading and source impedance absent.', 'DC operating point does not restore missing transient capacitor state in receiver replay.'])
(P/'evidence/lo-selfbias-ac.json').write_text(json.dumps(out,indent=2)+'\n');print(values);print(response)
