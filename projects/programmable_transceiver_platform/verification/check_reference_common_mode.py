"""Diagnostic common-mode envelope; no changed reference target adopted."""
import hashlib,json,re
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-reference-pair-common-mode-dc';B=R/'scratch/transceiver-reference-pair-device-dc'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());assert r['sources_before']==r['sources_after']
assert {c['name'] for c in r['cases']}=={'forward','reverse'}
arrays=[];rows=[]
for c in r['cases']:
 name=c['name'];assert c['returncode']==0
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(name+ext))==h
 log=(W/(name+'.log')).read_text().lower();assert not any(x in log for x in ('warning','error','aborted'))
 d=(W/(name+'.spice')).read_text();b=(B/'VH.spice').read_text()
 canonical=lambda s: re.sub(r'^wrdata \S+', 'wrdata OUTPUT', re.sub(r'^dc VH .*$', 'dc VH SWEEP', s,flags=re.M),flags=re.M)
 assert canonical(d)==canonical(b)
 with (W/(name+'.dat')).open() as f:h=f.readline().lower().split()
 a=np.loadtxt(W/(name+'.dat'),skiprows=1);assert a.shape==(91,len(h)) and np.isfinite(a).all()
 a=a[np.argsort(a[:,0])];assert np.allclose(a[:,0],np.linspace(1.5,2.4,91),atol=1e-12,rtol=0)
 arrays.append(a);v=lambda n:a[:,h.index(n)]
 margin=v('@m.xdut.xhigh.xt.m0[vds]')-v('@m.xdut.xhigh.xt.m0[vdsat]')
 # Confirm raw PMOS VDS convention against physical VDD-to-tail voltage.
 assert np.max(abs(v('@m.xdut.xhigh.xt.m0[vds]')-(3.3-v('v(xdut.xhigh.t)'))))<1e-9
 crossings=[list(map(float,a[i:i+2,0])) for i in range(90) if margin[i]*margin[i+1]<0]
 points=[]
 for target in (1.5,1.8,2.,2.15,2.4):
  k=int(np.argmin(abs(a[:,0]-target)))
  points.append(dict(target_v=target,output_error_mv=float((v('v(oh)')[k]-target)*1e3),tail_margin_v=float(margin[k]),power_mw=float(-3.3*v('i(vdd)')[k]*1e3)))
 rows.append(dict(direction=name,tail_margin_zero_brackets_v=crossings,points=points))
out=dict(completed=True,scope='nominal unloaded DC common-mode diagnostic',cases=rows,
 reverse_sweep_max_output_difference_v=float(abs(arrays[0][:,h.index('v(oh)')]-arrays[1][:,h.index('v(oh)')]).max()),
 provenance=r,limitations=['Changing reference target changes ADC span and interface requirements; no target change adopted.',
 'Positive tail margin alone does not qualify other devices, regulation, dynamic stability, noise or PVT.',
 'Ideal target/bias sources and zero external load; this is not an uncertainty bound.'])
(P/'evidence/reference-common-mode.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='provenance'},indent=2))
