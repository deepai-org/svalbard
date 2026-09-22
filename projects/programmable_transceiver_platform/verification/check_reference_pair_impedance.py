#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform';W=R/'scratch/transceiver-reference-pair-impedance'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((W/'result.json').read_text());assert {x['name'] for x in r['cases']}=={'baseline_h','baseline_l','long_mirror_h','long_mirror_l'};rows=[]
for c in r['cases']:
 n=c['name'];assert c['returncode']==0 and c['sources_before']==c['sources_after']
 for ext,h in c['artifacts_sha256'].items():assert sha(W/(n+ext))==h
 log=(W/(n+'.log')).read_text().lower();assert not any(x in log for x in ['warning','error','aborted'])
 with (W/(n+'.dat')).open() as f:assert f.readline().lower().split()==['frequency','zr','zi']
 a=np.loadtxt(W/(n+'.dat'),skiprows=1);assert a.shape==(481,3) and np.isfinite(a).all() and np.all(np.diff(a[:,0])>0) and np.isclose(a[-1,0],1e9)
 z=abs(a[:,1]+1j*a[:,2]);k=int(z.argmax());rows.append(dict(name=n,low_frequency_ohm=float(z[0]),peak_ohm=float(z[k]),peak_hz=float(a[k,0]),impedance_ohm={str(f):float(np.interp(np.log10(f),np.log10(a[:,0]),z)) for f in (1e6,5e6,20e6,50e6,100e6,200e6)}))
out=dict(completed=True,cases=rows,provenance=r,limitations=['Zero external DC load, small-signal closed-loop output impedance only; not loop gain or phase margin.','Actual2048unit reservoir per rail; no switched ADC, package or supply interaction.','Interpolated named frequencies use log-frequency magnitude interpolation.','Does not reverse rejection of longer mirrors under actual switched load.'])
(P/'evidence/reference-pair-impedance.json').write_text(json.dumps(out,indent=2)+'\n');print(rows)
