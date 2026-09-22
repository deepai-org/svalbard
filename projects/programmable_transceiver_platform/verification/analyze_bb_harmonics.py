#!/usr/bin/env python3
"""Selected IF harmonic fit; not total distortion, noise, or modulated EVM."""
import hashlib,json
from pathlib import Path
import numpy as np
from rf_tone_fit import fit
R=Path(__file__).resolve().parents[3];P=R/'projects/programmable_transceiver_platform'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
# Validate separation of a noncoherent harmonic pair before applying to exported data.
t=np.linspace(240e-9,400e-9,16001);f=20e6
z,_=fit(t,.01*np.cos(2*np.pi*f*t)+.0001*np.sin(4*np.pi*f*t),[2*f,f,3*f])
assert abs(z+.0001j)<1e-12
rows=[];provenance={}
for name in ('bb-connected-bypass','bb-connected-level10'):
 ap=P/'evidence'/(name+'.json');fp=P/'evidence'/(name+'-conversion.json')
 a=json.loads(ap.read_text());summary=json.loads(fp.read_text())
 assert a['completed'] and summary['completed'] and summary['audit_sha256']==sha(ap)
 provenance[name]=dict(audit_sha256=sha(ap),analysis_sha256=sha(fp))
 work=R/'scratch'/('transceiver-'+name)
 for c in a['provenance']['cases']:
  path=work/(c['name']+'.dat');assert sha(path)==c['artifacts_sha256']['.dat']
  with path.open() as stream:h=stream.readline().lower().split()
  raw=np.loadtxt(path,skiprows=1)
  for window in ([240,400],[320,400]):
   q=next(x for case in summary['cases'] if case['name']==c['name'] for x in case['fits'] if x['window_ns']==window and x['lo_harmonic_fit_order']==8)
   lo=q['lo_frequency_hz'];f=q['if_frequency_hz'];rf=lo+f
   w=raw[(raw[:,0]>=window[0]*1e-9)&(raw[:,0]<=window[1]*1e-9)];t=w[:,0]
   freqs=[f,2*f,3*f]+[n*lo for n in range(1,9)]+[rf,rf+lo]
   for channel,plus,minus in (('i','fip','fin'),('q','fqp','fqn')):
    y=w[:,h.index('v('+plus+')')]-w[:,h.index('v('+minus+')')]
    harmonics=[]
    for target in (f,2*f,3*f):
     z,res=fit(t,y,[target]+[x for x in freqs if x!=target]);harmonics.append(float(abs(z)))
    rows.append(dict(fixture=name,case=c['name'],window_ns=window,channel=channel,harmonic_peak_v=harmonics,second_third_rss_over_fundamental=float(np.hypot(*harmonics[1:])/harmonics[0]) if c['amplitude_v'] else None,residual_rms_v=res))
out=dict(completed=True,provenance=provenance,cases=rows,limitations=['Only second/third IF harmonics fitted; not THD, intermodulation, noise or EVM.','Finite short noncoherent windows; compare zero controls and window sensitivity before interpreting small components.','No acceptance threshold allocated; diagnostic only.'])
(P/'evidence/bb-level10-harmonics.json').write_text(json.dumps(out,indent=2)+'\n');print('harmonic analysis complete')
